#!/usr/bin/env python
"""
Comprehensive cleanup script for GCP test resources.

Removes all test-related resources from the GCP project:
- Cloud Functions (zip-test-*, proc-test-*, tf-e2e-gcp-*)
- Cloud Run services and revisions
- Storage buckets
- Pub/Sub topics and subscriptions
- Artifact Registry Docker images
- Cloud Scheduler jobs
"""
import os
import sys
from pathlib import Path

# Set credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/app/upload/template/gcp_credentials.json"

PROJECT_ID = "digital-twin-dev-481720"
REGION = "europe-west1"
TEST_PREFIXES = ["tf-e2e-gcp", "zip-test", "proc-test"]

print("=" * 60)
print("  GCP COMPREHENSIVE RESOURCE CLEANUP")
print("=" * 60)
print(f"Project: {PROJECT_ID}")
print(f"Region: {REGION}")
print(f"Prefixes: {TEST_PREFIXES}")
print()

# Track what we delete
deleted = {
    "functions": 0,
    "run_services": 0,
    "topics": 0,
    "subscriptions": 0,
    "buckets": 0,
    "schedulers": 0,
    "docker_images": 0
}
errors = []

def matches_prefix(name):
    """Check if name matches any test prefix."""
    return any(prefix in name for prefix in TEST_PREFIXES)

# 1. Delete Cloud Functions
print("[1/7] Deleting Cloud Functions...")
try:
    from google.cloud import functions_v2
    client = functions_v2.FunctionServiceClient()
    parent = f"projects/{PROJECT_ID}/locations/{REGION}"
    
    for func in client.list_functions(parent=parent):
        if matches_prefix(func.name):
            func_name = func.name.split("/")[-1]
            print(f"  Deleting function: {func_name}")
            try:
                op = client.delete_function(name=func.name)
                op.result(timeout=120)
                deleted["functions"] += 1
                print(f"    ✓ Deleted")
            except Exception as e:
                errors.append(f"Function {func_name}: {e}")
                print(f"    ✗ Error: {e}")
except Exception as e:
    errors.append(f"List functions: {e}")
    print(f"  ✗ Error listing functions: {e}")

# 2. Delete Cloud Run services
print("\n[2/7] Deleting Cloud Run services...")
try:
    from google.cloud import run_v2
    client = run_v2.ServicesClient()
    parent = f"projects/{PROJECT_ID}/locations/{REGION}"
    
    for service in client.list_services(parent=parent):
        if matches_prefix(service.name):
            svc_name = service.name.split("/")[-1]
            print(f"  Deleting service: {svc_name}")
            try:
                op = client.delete_service(name=service.name)
                op.result(timeout=120)
                deleted["run_services"] += 1
                print(f"    ✓ Deleted")
            except Exception as e:
                errors.append(f"Service {svc_name}: {e}")
                print(f"    ✗ Error: {e}")
except ImportError:
    print(f"  ⚠ Cloud Run library not available, skipping...")
except Exception as e:
    errors.append(f"Cloud Run cleanup: {e}")
    print(f"  ✗ Error with Cloud Run: {e}")

# 3. Delete Pub/Sub Topics and Subscriptions
print("\n[3/7] Deleting Pub/Sub topics and subscriptions...")
try:
    from google.cloud import pubsub_v1
    
    # Delete subscriptions first
    subscriber = pubsub_v1.SubscriberClient()
    project_path = f"projects/{PROJECT_ID}"
    
    for subscription in subscriber.list_subscriptions(request={"project": project_path}):
        if matches_prefix(subscription.name):
            sub_name = subscription.name.split("/")[-1]
            print(f"  Deleting subscription: {sub_name}")
            try:
                subscriber.delete_subscription(request={"subscription": subscription.name})
                deleted["subscriptions"] += 1
                print(f"    ✓ Deleted")
            except Exception as e:
                errors.append(f"Subscription {sub_name}: {e}")
                print(f"    ✗ Error: {e}")
    
    # Delete topics
    publisher = pubsub_v1.PublisherClient()
    for topic in publisher.list_topics(request={"project": project_path}):
        if matches_prefix(topic.name):
            topic_name = topic.name.split("/")[-1]
            print(f"  Deleting topic: {topic_name}")
            try:
                publisher.delete_topic(request={"topic": topic.name})
                deleted["topics"] += 1
                print(f"    ✓ Deleted")
            except Exception as e:
                errors.append(f"Topic {topic_name}: {e}")
                print(f"    ✗ Error: {e}")
except Exception as e:
    errors.append(f"Pub/Sub cleanup: {e}")
    print(f"  ✗ Error with Pub/Sub: {e}")

# 4. Delete Cloud Scheduler Jobs
print("\n[4/7] Deleting Cloud Scheduler jobs...")
try:
    from google.cloud import scheduler_v1
    client = scheduler_v1.CloudSchedulerClient()
    parent = f"projects/{PROJECT_ID}/locations/{REGION}"
    
    for job in client.list_jobs(parent=parent):
        if matches_prefix(job.name):
            job_name = job.name.split("/")[-1]
            print(f"  Deleting scheduler job: {job_name}")
            try:
                client.delete_job(name=job.name)
                deleted["schedulers"] += 1
                print(f"    ✓ Deleted")
            except Exception as e:
                errors.append(f"Scheduler {job_name}: {e}")
                print(f"    ✗ Error: {e}")
except ImportError:
    print(f"  ⚠ Cloud Scheduler library not available, skipping...")
except Exception as e:
    errors.append(f"Scheduler cleanup: {e}")
    print(f"  ✗ Error with Scheduler: {e}")

# 5. Delete Storage Buckets
print("\n[5/7] Deleting Storage buckets...")
try:
    from google.cloud import storage
    client = storage.Client(project=PROJECT_ID)
    
    for bucket in client.list_buckets():
        if matches_prefix(bucket.name):
            print(f"  Deleting bucket: {bucket.name}")
            try:
                # Delete all objects first
                blobs = list(bucket.list_blobs())
                if blobs:
                    print(f"    Deleting {len(blobs)} objects...")
                    bucket.delete_blobs(blobs)
                # Delete bucket
                bucket.delete()
                deleted["buckets"] += 1
                print(f"    ✓ Deleted")
            except Exception as e:
                errors.append(f"Bucket {bucket.name}: {e}")
                print(f"    ✗ Error: {e}")
except Exception as e:
    errors.append(f"Storage cleanup: {e}")
    print(f"  ✗ Error with Storage: {e}")

# 6. Delete Artifact Registry Docker Images
print("\n[6/7] Deleting Artifact Registry Docker images...")
try:
    from google.cloud import artifactregistry_v1
    client = artifactregistry_v1.ArtifactRegistryClient()
    
    # List repositories
    parent = f"projects/{PROJECT_ID}/locations/{REGION}"
    for repo in client.list_repositories(parent=parent):
        repo_name = repo.name.split("/")[-1]
        print(f"  Checking repository: {repo_name}")
        
        # List Docker images in this repository
        try:
            for image in client.list_docker_images(parent=repo.name):
                image_name = image.name
                # Check if image name contains test prefixes
                if matches_prefix(image_name):
                    short_name = image_name.split("/")[-1][:60]  # Truncate for display
                    print(f"    Deleting image: {short_name}...")
                    try:
                        client.delete_version(name=image_name)
                        deleted["docker_images"] += 1
                        print(f"      ✓ Deleted")
                    except Exception as e:
                        errors.append(f"Image {short_name}: {e}")
                        print(f"      ✗ Error: {e}")
        except Exception as e:
            print(f"    ⚠ Could not list images: {e}")
            
except ImportError:
    print(f"  ⚠ Artifact Registry library not available, skipping...")
except Exception as e:
    errors.append(f"Artifact Registry cleanup: {e}")
    print(f"  ✗ Error with Artifact Registry: {e}")

# 7. Summary
print("\n" + "=" * 60)
print("  CLEANUP SUMMARY")
print("=" * 60)
print(f"Cloud Functions deleted: {deleted['functions']}")
print(f"Cloud Run services deleted: {deleted['run_services']}")
print(f"Pub/Sub topics deleted: {deleted['topics']}")
print(f"Pub/Sub subscriptions deleted: {deleted['subscriptions']}")
print(f"Cloud Scheduler jobs deleted: {deleted['schedulers']}")
print(f"Storage buckets deleted: {deleted['buckets']}")
print(f"Docker images deleted: {deleted['docker_images']}")

if errors:
    print(f"\n⚠️  {len(errors)} errors occurred:")
    for error in errors[:10]:  # Show first 10 errors
        print(f"  - {error}")
    if len(errors) > 10:
        print(f"  ... and {len(errors) - 10} more errors")
    sys.exit(1)
else:
    print("\n✓ Cleanup completed successfully")
    sys.exit(0)
