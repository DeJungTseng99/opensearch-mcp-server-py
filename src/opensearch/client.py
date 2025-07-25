# Copyright OpenSearch Contributors
# SPDX-License-Identifier: Apache-2.0

import boto3
import logging
import os
from mcp_server_opensearch.clusters_information import ClusterInfo, get_cluster
from opensearchpy import OpenSearch, RequestsHttpConnection
import ssl
import urllib3

# Force disable SSL warnings and verification globally
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
ssl._create_default_https_context = ssl._create_unverified_context
from requests_aws4auth import AWS4Auth
from tools.tool_params import baseToolArgs
from typing import Any, Dict
from urllib.parse import urlparse


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
OPENSEARCH_SERVICE = 'es'
OPENSEARCH_SERVERLESS_SERVICE = 'aoss'

# global profile variable from command line
arg_profile = None


def set_profile(profile: str) -> None:
    global arg_profile
    arg_profile = profile


def is_serverless(args_or_cluster_info: baseToolArgs | ClusterInfo | None = None) -> bool:
    """Check if the OpenSearch instance is serverless.

    Args:
        args_or_cluster_info: Either baseToolArgs, ClusterInfo, or None

    Returns:
        bool: True if serverless, False otherwise
    """
    cluster_info = None

    # Handle baseToolArgs input
    if isinstance(args_or_cluster_info, baseToolArgs):
        if args_or_cluster_info and args_or_cluster_info.opensearch_cluster_name:
            cluster_info = get_cluster(args_or_cluster_info.opensearch_cluster_name)
    # Handle ClusterInfo input
    elif isinstance(args_or_cluster_info, ClusterInfo):
        cluster_info = args_or_cluster_info

    # Check cluster_info first
    if cluster_info:
        return cluster_info.is_serverless

    # If cluster_info is not provided, check the environment variable
    return os.getenv('AWS_OPENSEARCH_SERVERLESS', '').lower() == 'true'


def initialize_client_with_cluster(cluster_info: ClusterInfo = None) -> OpenSearch:
    """Initialize and return an OpenSearch client with appropriate authentication.

    The function attempts to authenticate in the following order:
    1. Basic authentication using OPENSEARCH_USERNAME and OPENSEARCH_PASSWORD
    2. AWS IAM authentication using boto3 credentials
       - Uses 'aoss' service name if OPENSEARCH_SERVERLESS=true
       - Uses 'es' service name otherwise

    Args:
        cluster_info (ClusterInfo): Cluster information object containing authentication and connection details

    Returns:
        OpenSearch: An initialized OpenSearch client instance.

    Raises:
        ValueError: If opensearch_url is empty or invalid
        RuntimeError: If no valid authentication method is available
    """
    opensearch_url = (
        cluster_info.opensearch_url if cluster_info else os.getenv('OPENSEARCH_URL', '')
    )
    if not opensearch_url:
        raise ValueError(
            'OpenSearch URL must be provided using config file or OPENSEARCH_URL environment variable'
        )
    opensearch_username = (
        cluster_info.opensearch_username if cluster_info else os.getenv('OPENSEARCH_USERNAME', '')
    )
    opensearch_password = (
        cluster_info.opensearch_password if cluster_info else os.getenv('OPENSEARCH_PASSWORD', '')
    )
    aws_region = cluster_info.aws_region if cluster_info else ''
    iam_arn = cluster_info.iam_arn if cluster_info else os.getenv('AWS_IAM_ARN', '')
    profile = cluster_info.profile if cluster_info else arg_profile
    if not profile:
        profile = os.getenv('AWS_PROFILE', '')

    # Check if using OpenSearch Serverless
    is_serverless_mode = is_serverless(cluster_info)
    service_name = OPENSEARCH_SERVERLESS_SERVICE if is_serverless_mode else OPENSEARCH_SERVICE

    if is_serverless_mode:
        logger.info('Using OpenSearch Serverless with service name: aoss')

    # Parse the OpenSearch domain URL
    parsed_url = urlparse(opensearch_url)

    # Determine SSL verification setting - cluster config takes precedence over environment
    verify_certs = True  # Default to True for security
    if cluster_info and cluster_info.verify_certs is not None:
        verify_certs = cluster_info.verify_certs
        logger.info(f'[SSL] Using cluster verify_certs setting: {verify_certs}')
    else:
        verify_certs = os.getenv('OPENSEARCH_SSL_VERIFY', 'true').lower() != 'false'
        logger.info(f'[SSL] Using environment verify_certs setting: {verify_certs}')
    
    logger.info(f'[SSL] Final verify_certs setting: {verify_certs} for URL: {opensearch_url}')

    # Common client configuration
    client_kwargs: Dict[str, Any] = {
        'hosts': [opensearch_url],
        'use_ssl': (parsed_url.scheme == 'https'),
        'verify_certs': verify_certs,
        'connection_class': RequestsHttpConnection,
    }
    
    # Additional SSL configuration when verify_certs is False (equivalent to curl -k)
    if not verify_certs and parsed_url.scheme == 'https':
        import ssl
        import urllib3
        logger.info('[SSL] Applying SSL bypass configuration (equivalent to curl -k)')
        
        # Disable SSL warnings when verification is disabled
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # For OpenSearch-py 3.0.0, use ssl_assert_hostname and ssl_assert_fingerprint
        client_kwargs['ssl_assert_hostname'] = False
        client_kwargs['ssl_assert_fingerprint'] = None
        
        # Create SSL context that ignores certificate errors
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # Add SSL context to client configuration
        client_kwargs['ssl_context'] = ssl_context
        client_kwargs['ssl_show_warn'] = False
        
        logger.info(f'[SSL] SSL bypass configuration applied: ssl_context.verify_mode = {ssl_context.verify_mode}')
        logger.info(f'[SSL] Client kwargs: {list(client_kwargs.keys())}')

    session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    if not aws_region:
        aws_region = session.region_name or os.getenv('AWS_REGION', '')

    # 1. Try IAM auth
    if iam_arn:
        logger.info(f'[IAM AUTH] Using IAM role authentication: {iam_arn}')
        try:
            if not aws_region:
                raise RuntimeError(
                    'AWS region not found, please specify region using `aws configure`'
                )

            sts_client = session.client('sts', region_name=aws_region)
            assumed_role = sts_client.assume_role(
                RoleArn=iam_arn, RoleSessionName='OpenSearchClientSession'
            )
            credentials = assumed_role['Credentials']

            aws_auth = AWS4Auth(
                credentials['AccessKeyId'],
                credentials['SecretAccessKey'],
                aws_region,
                service_name,
                session_token=credentials['SessionToken'],
            )
            client_kwargs['http_auth'] = aws_auth
            return OpenSearch(**client_kwargs)
        except Exception as e:
            logger.error(f'[IAM AUTH] Failed to assume IAM role {iam_arn}: {str(e)}')

    # 2. Try basic auth
    if opensearch_username and opensearch_password:
        logger.info(f'[BASIC AUTH] Using basic authentication: {opensearch_username}')
        client_kwargs['http_auth'] = (opensearch_username, opensearch_password)
        return OpenSearch(**client_kwargs)

    # 3. Try to get credentials from boto3 session
    try:
        logger.info(f'[AWS CREDS] Using AWS credentials authentication')
        credentials = session.get_credentials()
        if not aws_region:
            raise RuntimeError('AWS region not found, please specify region using `aws configure`')
        if credentials:
            aws_auth = AWS4Auth(
                refreshable_credentials=credentials,
                service=service_name,
                region=aws_region,
            )
            client_kwargs['http_auth'] = aws_auth
            return OpenSearch(**client_kwargs)
    except (boto3.exceptions.Boto3Error, Exception) as e:
        logger.error(f'[AWS CREDS] Failed to get AWS credentials: {str(e)}')

    # 4. Try no authentication (for local development)
    logger.info('[NO AUTH] Using no authentication (local development mode)')
    return OpenSearch(**client_kwargs)


def initialize_client(args: baseToolArgs) -> OpenSearch:
    """Initialize and return an OpenSearch client with appropriate authentication.

    This function gets cluster information from the provided arguments and then
    initializes the OpenSearch client using that information.

    Args:
        args (baseToolArgs): The arguments object containing authentication and connection details

    Returns:
        OpenSearch: An initialized OpenSearch client instance.

    Raises:
        ValueError: If opensearch_url is empty or invalid
        RuntimeError: If no valid authentication method is available
    """
    cluster_info = None
    if args and args.opensearch_cluster_name:
        cluster_info = get_cluster(args.opensearch_cluster_name)
    else:
        # If no cluster name specified, use the first available cluster in multi-mode
        from mcp_server_opensearch.clusters_information import cluster_registry
        if cluster_registry:
            first_cluster_name = next(iter(cluster_registry))
            cluster_info = cluster_registry[first_cluster_name]
            logger.info(f'No cluster specified, using first available cluster: {first_cluster_name}')
    return initialize_client_with_cluster(cluster_info)
