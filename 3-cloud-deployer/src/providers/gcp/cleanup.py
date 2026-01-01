"""
GCP SDK Cleanup Module.

Provides fallback cleanup for GCP resources that may be orphaned after
Terraform destroy fails or misses resources.
"""
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def cleanup_gcp_resources(
    credentials: dict, 
    prefix: str, 
    dry_run: bool = False
) -> None:
    """
    Clean up GCP resources matching prefix.
    
    Args:
        credentials: Dict with GCP credentials
        prefix: Resource name prefix (e.g., 'tf-e2e-gcp')
        dry_run: Log what would be deleted without deleting
        
    Resources cleaned:
        - Cloud Functions (Gen 2)
        - Pub/Sub Topics
        - Pub/Sub Subscriptions
        - Firestore collections
        - Cloud Storage buckets
        - Cloud Workflows
        - Service Accounts
    """
    from google.oauth2 import service_account
    from googleapiclient import discovery
    
    gcp_creds = credentials.get("gcp", {})
    project_id = gcp_creds.get("gcp_project_id")
    region = gcp_creds.get("gcp_region", "europe-west1")
    
    if not project_id:
        logger.info("[GCP SDK] No project_id found, skipping cleanup")
        return
    
    # Build credentials from service account info
    try:
        if "gcp_service_account_key" in gcp_creds:
            sa_key = gcp_creds["gcp_service_account_key"]
            if isinstance(sa_key, str):
                sa_key = json.loads(sa_key)
            gcp_credentials = service_account.Credentials.from_service_account_info(sa_key)
        else:
            logger.info("[GCP SDK] No service account key found, skipping cleanup")
            return
    except Exception as e:
        logger.warning(f"[GCP SDK] Error creating credentials: {e}")
        return
    
    prefix_underscore = prefix.replace("-", "_")
    
    logger.info(f"[GCP SDK] Fallback cleanup for prefix: {prefix}")
    logger.info(f"[GCP SDK] Project: {project_id}, Region: {region}")
    if dry_run:
        logger.info("[GCP SDK] DRY RUN MODE - no resources will be deleted")
    
    # 1. Cloud Functions (Gen 2) - with pagination
    logger.info("[Cloud Functions] Checking for orphans...")
    try:
        functions_client = discovery.build('cloudfunctions', 'v2', credentials=gcp_credentials)
        parent = f"projects/{project_id}/locations/{region}"
        
        page_token = None
        while True:
            if page_token:
                result = functions_client.projects().locations().functions().list(parent=parent, pageToken=page_token).execute()
            else:
                result = functions_client.projects().locations().functions().list(parent=parent).execute()
            
            for func in result.get('functions', []):
                func_name = func['name'].split('/')[-1]
                if prefix in func_name or prefix_underscore in func_name:
                    logger.info(f"  Found orphan: {func_name}")
                    if dry_run:
                        logger.info(f"    [DRY RUN] Would delete")
                    else:
                        try:
                            functions_client.projects().locations().functions().delete(name=func['name']).execute()
                            logger.info(f"    ✓ Deleted")
                        except Exception as e:
                            logger.warning(f"    ✗ Error: {e}")
            
            page_token = result.get('nextPageToken')
            if not page_token:
                break
    except Exception as e:
        logger.warning(f"  Error: {e}")
    
    # 2. Pub/Sub Topics - with pagination
    logger.info("[Pub/Sub Topics] Checking for orphans...")
    try:
        pubsub_client = discovery.build('pubsub', 'v1', credentials=gcp_credentials)
        project_path = f"projects/{project_id}"
        
        page_token = None
        while True:
            if page_token:
                result = pubsub_client.projects().topics().list(project=project_path, pageToken=page_token).execute()
            else:
                result = pubsub_client.projects().topics().list(project=project_path).execute()
            
            for topic in result.get('topics', []):
                topic_name = topic['name'].split('/')[-1]
                if prefix in topic_name or prefix_underscore in topic_name:
                    logger.info(f"  Found orphan: {topic_name}")
                    if dry_run:
                        logger.info(f"    [DRY RUN] Would delete")
                    else:
                        try:
                            pubsub_client.projects().topics().delete(topic=topic['name']).execute()
                            logger.info(f"    ✓ Deleted")
                        except Exception as e:
                            logger.warning(f"    ✗ Error: {e}")
            
            page_token = result.get('nextPageToken')
            if not page_token:
                break
    except Exception as e:
        logger.warning(f"  Error: {e}")
    
    # 3. Pub/Sub Subscriptions - with pagination
    logger.info("[Pub/Sub Subscriptions] Checking for orphans...")
    try:
        pubsub_client = discovery.build('pubsub', 'v1', credentials=gcp_credentials)
        project_path = f"projects/{project_id}"
        
        page_token = None
        while True:
            if page_token:
                result = pubsub_client.projects().subscriptions().list(project=project_path, pageToken=page_token).execute()
            else:
                result = pubsub_client.projects().subscriptions().list(project=project_path).execute()
            
            for sub in result.get('subscriptions', []):
                sub_name = sub['name'].split('/')[-1]
                if prefix in sub_name or prefix_underscore in sub_name:
                    logger.info(f"  Found orphan: {sub_name}")
                    if dry_run:
                        logger.info(f"    [DRY RUN] Would delete")
                    else:
                        try:
                            pubsub_client.projects().subscriptions().delete(subscription=sub['name']).execute()
                            logger.info(f"    ✓ Deleted")
                        except Exception as e:
                            logger.warning(f"    ✗ Error: {e}")
            
            page_token = result.get('nextPageToken')
            if not page_token:
                break
    except Exception as e:
        logger.warning(f"  Error: {e}")
    
    # 4. Firestore (delete collections matching prefix)
    logger.info("[Firestore] Checking for orphan collections...")
    try:
        from google.cloud import firestore
        
        db = firestore.Client(project=project_id, credentials=gcp_credentials)
        
        collections = db.collections()
        for collection in collections:
            if prefix in collection.id or prefix_underscore in collection.id:
                logger.info(f"  Found orphan collection: {collection.id}")
                if dry_run:
                    logger.info(f"    [DRY RUN] Would delete all documents")
                else:
                    try:
                        docs = collection.stream()
                        for doc in docs:
                            doc.reference.delete()
                        logger.info(f"    ✓ Deleted all documents")
                    except Exception as e:
                        logger.warning(f"    ✗ Error: {e}")
    except ImportError:
        logger.info("  google-cloud-firestore not installed, skipping")
    except Exception as e:
        logger.warning(f"  Error: {e}")
    
    # 5. Cloud Storage Buckets - with pagination
    logger.info("[Cloud Storage] Checking for orphan buckets...")
    try:
        storage_client = discovery.build('storage', 'v1', credentials=gcp_credentials)
        
        page_token = None
        while True:
            if page_token:
                result = storage_client.buckets().list(project=project_id, pageToken=page_token).execute()
            else:
                result = storage_client.buckets().list(project=project_id).execute()
            
            for bucket in result.get('items', []):
                bucket_name = bucket['name']
                if prefix in bucket_name or prefix_underscore in bucket_name:
                    logger.info(f"  Found orphan: {bucket_name}")
                    if dry_run:
                        logger.info(f"    [DRY RUN] Would delete bucket and contents")
                    else:
                        try:
                            # First delete all objects in bucket (with pagination)
                            obj_page_token = None
                            while True:
                                if obj_page_token:
                                    objects = storage_client.objects().list(bucket=bucket_name, pageToken=obj_page_token).execute()
                                else:
                                    objects = storage_client.objects().list(bucket=bucket_name).execute()
                                
                                for obj in objects.get('items', []):
                                    storage_client.objects().delete(bucket=bucket_name, object=obj['name']).execute()
                                
                                obj_page_token = objects.get('nextPageToken')
                                if not obj_page_token:
                                    break
                            
                            # Then delete bucket
                            storage_client.buckets().delete(bucket=bucket_name).execute()
                            logger.info(f"    ✓ Deleted")
                        except Exception as e:
                            logger.warning(f"    ✗ Error: {e}")
            
            page_token = result.get('nextPageToken')
            if not page_token:
                break
    except Exception as e:
        logger.warning(f"  Error: {e}")
    
    # 6. Cloud Workflows (state machine equivalent)
    logger.info("[Cloud Workflows] Checking for orphans...")
    try:
        workflows_client = discovery.build('workflows', 'v1', credentials=gcp_credentials)
        parent = f"projects/{project_id}/locations/{region}"
        
        result = workflows_client.projects().locations().workflows().list(parent=parent).execute()
        for workflow in result.get('workflows', []):
            workflow_name = workflow['name'].split('/')[-1]
            if prefix in workflow_name or prefix_underscore in workflow_name:
                logger.info(f"  Found orphan: {workflow_name}")
                if dry_run:
                    logger.info(f"    [DRY RUN] Would delete")
                else:
                    try:
                        workflows_client.projects().locations().workflows().delete(name=workflow['name']).execute()
                        logger.info(f"    ✓ Deleted")
                    except Exception as e:
                        logger.warning(f"    ✗ Error: {e}")
    except Exception as e:
        logger.warning(f"  Error: {e}")
    
    # 7. Service Accounts (IAM equivalent)
    logger.info("[Service Accounts] Checking for orphans...")
    try:
        iam_client = discovery.build('iam', 'v1', credentials=gcp_credentials)
        
        result = iam_client.projects().serviceAccounts().list(name=f"projects/{project_id}").execute()
        for sa in result.get('accounts', []):
            sa_email = sa['email']
            sa_name = sa_email.split('@')[0]
            if prefix in sa_name or prefix_underscore in sa_name:
                logger.info(f"  Found orphan: {sa_email}")
                if dry_run:
                    logger.info(f"    [DRY RUN] Would delete")
                else:
                    try:
                        iam_client.projects().serviceAccounts().delete(name=f"projects/{project_id}/serviceAccounts/{sa_email}").execute()
                        logger.info(f"    ✓ Deleted")
                    except Exception as e:
                        logger.warning(f"    ✗ Error: {e}")
    except Exception as e:
        logger.warning(f"  Error: {e}")
    
    logger.info("[GCP SDK] Fallback cleanup complete")
