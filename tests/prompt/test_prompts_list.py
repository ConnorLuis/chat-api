from fastapi.testclient import TestClient
from src.app.main import app

client = TestClient(app)

"""
    测试/prompts，验证是否：
        status 200
        body 有 prompts
        prompts 是 dict
        至少包含 chat 和 qa_strict（如果你仓库确实有它们）
        versions 是 list 且非空
"""
def test_prompts_list_ok():

    r = client.get("/prompts")
    assert r.status_code == 200
    data = r.json()
    assert "prompts" in data
    assert isinstance(data["prompts"], dict)
    prompts_dict = data["prompts"]
    assert "chat" in prompts_dict
    assert isinstance(prompts_dict["chat"], list)
    assert len(prompts_dict["chat"]) > 0
    assert "qa_strict" in prompts_dict
    assert isinstance(prompts_dict["qa_strict"], list)
    assert len(prompts_dict["qa_strict"]) > 0
