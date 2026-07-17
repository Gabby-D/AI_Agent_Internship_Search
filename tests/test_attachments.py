import base64
import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
import urllib.request
import urllib.error
import pytest

from internship_search.review_ui import _build_handler


@pytest.fixture
def test_server(tmp_path):
    data_dir = tmp_path / "data"
    private_dir = tmp_path / "private"
    data_dir.mkdir()
    private_dir.mkdir()
    
    # Create empty activity log
    (data_dir / "activity_log.jsonl").write_text("", encoding="utf-8")

    handler_class = _build_handler(data_path=data_dir, private_path=private_dir)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_class)
    port = server.server_address[1]

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield {
        "port": port,
        "data_dir": data_dir,
        "private_dir": private_dir,
        "url": f"http://127.0.0.1:{port}"
    }

    server.shutdown()
    server.server_close()


def test_attachment_upload_and_download_flow(test_server):
    base_url = test_server["url"]
    
    # 1. GET /api/attachments should initially be empty
    req = urllib.request.Request(f"{base_url}/api/attachments")
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        assert data == {"attachments": []}

    # 2. POST /api/attachments/upload with a valid PDF file
    test_content = b"PDF dummy content"
    b64_content = base64.b64encode(test_content).decode("utf-8")
    
    upload_payload = {
        "filename": "test_resume.pdf",
        "content_base64": b64_content,
        "mime_type": "application/pdf"
    }
    
    req = urllib.request.Request(
        f"{base_url}/api/attachments/upload",
        data=json.dumps(upload_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        assert result == {"ok": True}

    # Verify file exists on disk in attachments folder
    saved_file = test_server["private_dir"] / "attachments" / "test_resume.pdf"
    assert saved_file.exists()
    assert saved_file.read_bytes() == test_content

    # 3. GET /api/attachments should now return the file
    req = urllib.request.Request(f"{base_url}/api/attachments")
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        assert len(data["attachments"]) == 1
        att = data["attachments"][0]
        assert att["filename"] == "test_resume.pdf"
        assert att["size_bytes"] == len(test_content)
        assert "date_uploaded" in att

    # 4. GET /api/attachments/download should serve the file correctly
    req = urllib.request.Request(f"{base_url}/api/attachments/download?filename=test_resume.pdf")
    with urllib.request.urlopen(req) as resp:
        assert resp.getheader("Content-Type") == "application/pdf"
        assert 'attachment; filename="test_resume.pdf"' in resp.getheader("Content-Disposition")
        assert resp.read() == test_content


def test_attachment_upload_size_limit(test_server):
    base_url = test_server["url"]
    
    # 5MB + 1 byte
    large_content = b"x" * (5 * 1024 * 1024 + 1)
    b64_content = base64.b64encode(large_content).decode("utf-8")
    
    upload_payload = {
        "filename": "huge_file.pdf",
        "content_base64": b64_content,
        "mime_type": "application/pdf"
    }
    
    req = urllib.request.Request(
        f"{base_url}/api/attachments/upload",
        data=json.dumps(upload_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        urllib.request.urlopen(req)
    
    assert excinfo.value.code == 400
    error_data = json.loads(excinfo.value.read().decode("utf-8"))
    assert "size" in error_data["error"].lower()


def test_attachment_upload_disallowed_extension(test_server):
    base_url = test_server["url"]
    
    upload_payload = {
        "filename": "malicious.exe",
        "content_base64": base64.b64encode(b"unsafe code").decode("utf-8"),
        "mime_type": "application/octet-stream"
    }
    
    req = urllib.request.Request(
        f"{base_url}/api/attachments/upload",
        data=json.dumps(upload_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        urllib.request.urlopen(req)
        
    assert excinfo.value.code == 400
    error_data = json.loads(excinfo.value.read().decode("utf-8"))
    assert "unsupported" in error_data["error"].lower() or "unsafe" in error_data["error"].lower()


def test_attachment_path_traversal_blocked(test_server):
    base_url = test_server["url"]
    
    # Attempting to upload to a path outside attachments folder
    upload_payload = {
        "filename": "../../../traversal_test.pdf",
        "content_base64": base64.b64encode(b"traversal").decode("utf-8"),
        "mime_type": "application/pdf"
    }
    
    # Note that Path(filename).name extracts 'traversal_test.pdf' safely
    req = urllib.request.Request(
        f"{base_url}/api/attachments/upload",
        data=json.dumps(upload_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        assert result == {"ok": True}
        
    # The file should be saved under 'attachments/traversal_test.pdf', NOT escaped
    assert not (test_server["private_dir"] / "traversal_test.pdf").exists()
    assert (test_server["private_dir"] / "attachments" / "traversal_test.pdf").exists()


def test_attachment_delete(test_server):
    base_url = test_server["url"]
    attachments_dir = test_server["private_dir"] / "attachments"
    attachments_dir.mkdir(exist_ok=True)
    
    test_file = attachments_dir / "to_delete.txt"
    test_file.write_text("goodbye", encoding="utf-8")
    
    # Confirm deletion via API
    delete_payload = {"filename": "to_delete.txt"}
    req = urllib.request.Request(
        f"{base_url}/api/attachments/delete",
        data=json.dumps(delete_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(resp := req) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        assert result == {"ok": True}
        
    assert not test_file.exists()
