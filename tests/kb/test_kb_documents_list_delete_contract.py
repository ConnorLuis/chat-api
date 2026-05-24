def test_kb_documents_list_and_delete_contract(client, isolated_kb_env):
    isolated_kb_env(collection_name="test_kb_docs_list_delete")

    d1 = client.post("/kb/documents", json={"title": "t1", "text": "aaa", "source": "test"}).json()["doc_id"]
    d2 = client.post("/kb/documents", json={"title": "t2", "text": "bbb", "source": "test"}).json()["doc_id"]

    r = client.get("/kb/documents", params={"limit": 50, "offset": 0})
    assert r.status_code == 200
    data = r.json()

    assert "items" in data and isinstance(data["items"], list)
    assert "total" in data and isinstance(data["total"], int)
    assert "metadata" in data
    assert isinstance(data["metadata"].get("trace_id"), str) and data["metadata"]["trace_id"].strip()

    doc_ids = [x["doc_id"] for x in data["items"]]
    assert d1 in doc_ids
    assert d2 in doc_ids

    # 删除
    rd = client.delete(f"/kb/documents/{d1}", params={"reason": "test"})
    assert rd.status_code == 200
    dd = rd.json()
    assert dd["doc_id"] == d1
    assert dd["deleted"] is True
    assert isinstance(dd["metadata"].get("trace_id"), str) and dd["metadata"]["trace_id"].strip()

    # 默认列表应隐藏删除doc
    r2 = client.get("/kb/documents", params={"limit": 50, "offset": 0})
    ids2 = [x["doc_id"] for x in r2.json()["items"]]
    assert d1 not in ids2

    # 加包含删除参数，则显示
    r3 = client.get("/kb/documents", params={"limit": 50, "offset": 0, "include_deleted": True})
    items3 = r3.json()["items"]
    rec = [x for x in items3 if x["doc_id"] == d1][0]
    assert rec["deleted"] is True