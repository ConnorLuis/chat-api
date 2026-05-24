def test_demo_page_has_rag_controls(client):
    r = client.get("/demo")
    assert r.status_code == 200
    html = r.text

    # 这些关键字按你页面实际显示的文案挑稳定的锁住
    assert "Use KB" in html or "RAG" in html
    assert "kb_top_k" in html
    assert "use_kb" in html
    assert "Citations" in html or "引用" in html
    assert "/chat/stream" in html
    assert "/chat" in html