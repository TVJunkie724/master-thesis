from src.providers.gcp import cleanup


def test_discovery_iterator_consumes_every_page():
    calls = []

    class Request:
        def __init__(self, response):
            self.response = response

        def execute(self):
            return self.response

    def list_method(**kwargs):
        calls.append(kwargs)
        if "pageToken" not in kwargs:
            return Request({"resources": ["one"], "nextPageToken": "next"})
        return Request({"resources": ["two"]})

    assert list(
        cleanup._discovery_items(
            list_method,
            "resources",
            parent="projects/demo",
        )
    ) == ["one", "two"]
    assert calls == [
        {"parent": "projects/demo"},
        {"parent": "projects/demo", "pageToken": "next"},
    ]


def test_discovery_iterator_handles_empty_result():
    class Request:
        def execute(self):
            return {}

    assert list(cleanup._discovery_items(lambda **kwargs: Request(), "items")) == []


def test_soft_deleted_custom_role_is_not_undeleted_or_deleted_again():
    class RolesApi:
        def delete(self, **kwargs):
            raise AssertionError("soft-deleted role must not be deleted again")

    deleted = cleanup._delete_custom_role(
        RolesApi(),
        {"name": "projects/demo/roles/factory", "deleted": True},
        dry_run=False,
    )

    assert deleted is False


def test_active_custom_role_is_deleted_once():
    calls = []

    class Request:
        def execute(self):
            calls.append("execute")

    class RolesApi:
        def delete(self, **kwargs):
            calls.append(kwargs)
            return Request()

    deleted = cleanup._delete_custom_role(
        RolesApi(),
        {"name": "projects/demo/roles/factory", "deleted": False},
        dry_run=False,
    )

    assert calls == [
        {"name": "projects/demo/roles/factory"},
        "execute",
    ]
    assert deleted is True


def test_bucket_drain_deletes_every_generation_without_page_tokens():
    list_calls = []
    delete_calls = []
    pages = [
        {
            "items": [
                {"name": "device.json", "generation": "2"},
                {"name": "device.json", "generation": "1"},
            ],
            "nextPageToken": "must-not-be-used-after-mutation",
        },
        {},
    ]

    class Request:
        def __init__(self, response=None, callback=None):
            self.response = response or {}
            self.callback = callback

        def execute(self):
            if self.callback:
                self.callback()
            return self.response

    class Objects:
        def list(self, **kwargs):
            list_calls.append(kwargs)
            return Request(pages.pop(0))

        def delete(self, **kwargs):
            return Request(callback=lambda: delete_calls.append(kwargs))

    class StorageClient:
        def objects(self):
            return Objects()

    cleanup._delete_all_bucket_objects(StorageClient(), "factory-bucket")

    assert list_calls == [
        {"bucket": "factory-bucket", "versions": True},
        {"bucket": "factory-bucket", "versions": True},
    ]
    assert delete_calls == [
        {"bucket": "factory-bucket", "object": "device.json", "generation": "2"},
        {"bucket": "factory-bucket", "object": "device.json", "generation": "1"},
    ]
