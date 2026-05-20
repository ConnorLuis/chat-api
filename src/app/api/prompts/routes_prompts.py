from pathlib import Path

from fastapi import APIRouter
from src.app.core.settings import settings
from src.app.llm.prompt_registry import PromptRegistry
from src.app.llm.schemas import PromptsListResponse

router = APIRouter()
prompt_registry = PromptRegistry(settings.PROMPTS_DIR)

@router.get("/prompts", response_model= PromptsListResponse)
def list_prompts():
    prompts_dir = Path(settings.PROMPTS_DIR)
    prompts: dict[str, list[str]] = {}
    if not prompts_dir.exists():
        return {"prompts": prompts}

    for prompt_dir in  prompts_dir.iterdir():
        if not prompt_dir.is_dir() or prompt_dir.name.startswith("."):
            continue
        versions: list[str] = []
        for f in prompt_dir.iterdir():
            if (f.is_file() and f.suffix.lower() == ".md" and not f.name.startswith(".")):
                versions.append(f.stem)
        versions.sort()
        prompts[prompt_dir.name] = versions
    return {"prompts": prompts}

