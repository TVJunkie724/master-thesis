#!/usr/bin/env python
"""
Comprehensive cleanup for GCP E2E test - includes Firestore and IAM.
"""
import os
import sys

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/app/upload/template/gcp_credentials.json"

PROJECT_ID = "digital-twin-dev-481720"
REGION = "europe-west1"
PREFIXES = ["tf-e2e-gcp", "tf-gcp"]

print("=" * 60)
print("  FULL GCP CLEANUP (including Firestore & IAM)")
print("=" * 60)
print(f"Project: {PROJECT_ID}")
print(f"Region: {REGION}")
print()

deleted = {"functions": 0, "run_services": 0, "topics": 0, "buckets": 0, "firestore": 0, "iam": 0}
errors = []

def matches(name):
    return any(p in name for p in PREFIXES)

# 1. Cloud Functions
print("[1/7] Deleting Cloud Functions...")
try:
    from google.cloud import functions_v2
    client = functions_v2.FunctionServiceClient()
    for func in client.list_functions(parent=f"projects/{PROJECT_ID}/locations/{REGION}"):
        if matches(func.name):
            print(f"  Deleting: {func.name.split('/')[-1]}")
            try:
                client.delete_function(name=func.name).result(timeout=120)
                deleted["functions"] += 1
                print("    ✓ Deleted")
            except Exception as e:
                errors.append(f"Function: {e}")
                print(f"    ✗ {e}")
except Exception as e:
    print(f"  ⚠ {e}")

# 2. Cloud Run services
print("\n[2/7] Deleting Cloud Run services...")
try:
    from google.cloud import run_v2
    client = run_v2.ServicesClient()
    for svc in client.list_services(parent=f"projects/{PROJECT_ID}/locations/{REGION}"):
        if matches(svc.name):
            print(f"  Deleting: {svc.name.split('/')[-1]}")
            try:
                client.delete_service(name=svc.name).result(timeout=120)
                deleted["run_services"] += 1
                print("    ✓ Deleted")
            except Exception as e:
                errors.append(f"Service: {e}")
                print(f"    ✗ {e}")
except ImportError:
    print("  ⚠ Library not available")
except Exception as e:
    print(f"  ⚠ {e}")

# 3. Pub/Sub
print("\n[3/7] Deleting Pub/Sub topics...")
try:
    from google.cloud import pubsub_v1
    publisher = pubsub_v1.PublisherClient()
    for topic in publisher.list_topics(request={"project": f"projects/{PROJECT_ID}"}):
        if matches(topic.name):
            print(f"  Deleting: {topic.name.split('/')[-1]}")
            try:
                publisher.delete_topic(request={"topic": topic.name})
                deleted["topics"] += 1
                print("    ✓ Deleted")
            except Exception as e:
                errors.append(f"Topic: {e}")
                print(f"    ✗ {e}")
except Exception as e:
    print(f"  ⚠ {e}")

# 4. Storage Buckets
print("\n[4/7] Deleting Storage buckets...")
try:
    from google.cloud import storage
    client = storage.Client(project=PROJECT_ID)
    for bucket in client.list_buckets():
        if matches(bucket.name):
            print(f"  Deleting: {bucket.name}")
            try:
                blobs = list(bucket.list_blobs())
                if blobs:
                    bucket.delete_blobs(blobs)
                bucket.delete()
                deleted["buckets"] += 1
                print("    ✓ Deleted")
            except Exception as e:
                errors.append(f"Bucket: {e}")
                print(f"    ✗ {e}")
except Exception as e:
    print(f"  ⚠ {e}")

# 5. Firestore (default) database
print("\n[5/7] Deleting Firestore database...")
try:
    from google.cloud.firestore_admin_v1 import FirestoreAdminClient
    client = FirestoreAdminClient()
    db_name = f"projects/{PROJECT_ID}/databases/(default)"
    print(f"  Deleting: (default)")
    try:
        client.delete_database(name=db_name)
        deleted["firestore"] += 1
        print("    ✓ Deleted")
    except Exception as e:
        if "NOT_FOUND" in str(e):
            print("    ⚠ Already deleted or doesn't exist")
        else:
            errors.append(f"Firestore: {e}")
            print(f"    ✗ {e}")
except ImportError:
    print("  ⚠ Library not available")
except Exception as e:
    print(f"  ⚠ {e}")

# 6. IAM Service Accounts and Custom Roles
print("\n[6/7] Deleting IAM resources...")
try:
    from google.cloud import iam_admin_v1
    from google.iam.admin.v1 import iam_pb2
    
    # Delete service accounts
    client = iam_admin_v1.IAMClient()
    for sa in client.list_service_accounts(name=f"projects/{PROJECT_ID}"):
        if matches(sa.email):
            print(f"  Deleting SA: {sa.email}")
            try:
                client.delete_service_account(name=sa.name)
                deleted["iam"] += 1
                print("    ✓ Deleted")
            except Exception as e:
                errors.append(f"SA: {e}")
                print(f"    ✗ {e}")
except ImportError:
    print("  ⚠ Library not available, trying alternative...")
    # Try using google.cloud.iam
    try:
        import google.auth
        from googleapiclient import discovery
        credentials, project = google.auth.default()
        service = discovery.build('iam', 'v1', credentials=credentials)
        
        # List and delete service accounts
        result = service.projects().serviceAccounts().list(
            name=f'projects/{PROJECT_ID}'
        ).execute()
        
        for sa in result.get('accounts', []):
            if matches(sa['email']):
                print(f"  Deleting SA: {sa['email']}")
                try:
                    service.projects().serviceAccounts().delete(
                        name=sa['name']
                    ).execute()
                    deleted["iam"] += 1
                    print("    ✓ Deleted")
                except Exception as e:
                    errors.append(f"SA: {e}")
                    print(f"    ✗ {e}")
        
        # Delete custom role
        role_id = "tf_e2e_gcp_functions_role"
        print(f"  Deleting role: {role_id}")
        try:
            service.projects().roles().delete(
                name=f'projects/{PROJECT_ID}/roles/{role_id}'
            ).execute()
            deleted["iam"] += 1
            print("    ✓ Deleted")
        except Exception as e:
            if "was not found" in str(e).lower():
                print("    ⚠ Already deleted")
            else:
                errors.append(f"Role: {e}")
                print(f"    ✗ {e}")
    except Exception as e:
        print(f"  ⚠ {e}")
except Exception as e:
    print(f"  ⚠ {e}")

# 7. Summary
print("\n" + "=" * 60)
print("  CLEANUP SUMMARY")
print("=" * 60)
print(f"Cloud Functions: {deleted['functions']}")
print(f"Cloud Run: {deleted['run_services']}")
print(f"Pub/Sub topics: {deleted['topics']}")
print(f"Storage buckets: {deleted['buckets']}")
print(f"Firestore: {deleted['firestore']}")
print(f"IAM resources: {deleted['iam']}")

if errors:
    print(f"\n⚠️  {len(errors)} errors")
else:
    print("\n✓ Cleanup complete")
