from __future__ import annotations

from pathlib import Path
from typing import Dict, Any
import json


# General FS helpers
def ensure_dir(p: Path) -> Path:
    """디렉터리가 존재하도록 보장한다.

    매개변수:
        p: 생성(보장)할 디렉터리 경로.

    반환값:
        입력과 동일한 경로 `p` (존재하도록 생성 후 반환).
    """
    p.mkdir(parents=True, exist_ok=True)
    return p


def write_json_output(data: Dict[str, Any], path: Path) -> None:
    """딕셔너리를 JSON 파일로 저장한다.

    상위 디렉터리를 먼저 생성한 뒤, UTF-8 인코딩과 들여쓰기를 적용해
    사람이 읽기 쉬운 JSON으로 기록한다.

    매개변수:
        data: JSON으로 직렬화 가능한 사전 객체.
        path: 저장할 대상 파일 경로.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _project_root_from_mypkg() -> Path:
    """이 파일의 위치로부터 프로젝트 루트를 추정한다.

    디렉터리 구조 가정:
        <project>/src/mypkg/core/io.py
    위 구조에서 프로젝트 루트는 이 파일로부터 상위 3단계 지점이다.

    반환값:
        추정된 프로젝트 루트의 절대 경로.
    """
    here = Path(__file__).resolve()
    parents = here.parents
    idx = 3 if len(parents) > 3 else (len(parents) - 1)
    return parents[idx]


def _resolve_from_mypkg_root(path: str | Path) -> Path:
    """프로젝트 루트를 기준으로 상대 경로를 절대 경로로 변환한다.

    매개변수:
        path: 절대 또는 상대 경로.

    반환값:
        절대 경로. 상대 경로 입력은 프로젝트 루트를 기준으로 해석한다.
    """
    p = Path(path)
    if p.is_absolute():
        return p
    return (_project_root_from_mypkg() / p).resolve()


def resolve_sanitized_path(sanitized_path: str | Path) -> Path:
    """sanitized(JSON) 파일 경로를 절대 경로로 반환한다. (별칭)

    상대 경로가 주어진 경우, `mypkg`의 위치로부터 추정한 프로젝트 루트를
    기준으로 절대 경로를 계산한다.

    매개변수:
        sanitized_path: 절대 또는 프로젝트 루트 기준 상대 경로.

    반환값:
        절대 경로(`Path`).
    """
    return _resolve_from_mypkg_root(sanitized_path)


def version_dir_from_sanitized(sanitized_path: str | Path) -> Path:
    """sanitized 파일 경로로부터 버전 디렉터리를 반환한다.

    구조 가정:
        <...>/processed/{document_type}/{version}/{base_name}/_sanitized/<file>.json
    여기서 버전 디렉터리는 `<...>/processed/{document_type}/{version}`.

    매개변수:
        sanitized_path: sanitized JSON 경로(절대 또는 상대).

    반환값:
        버전 디렉터리의 절대 경로(`Path`).
    """
    p = resolve_sanitized_path(sanitized_path)
    return p.parent.parent.parent


def base_dir_from_sanitized(sanitized_path: str | Path) -> Path:
    """sanitized 파일 경로로부터 베이스 디렉터리(`{base_name}`)를 반환한다.

    구조: `<...>/{version}/{base_name}/_sanitized/<file>.json` 에서 `{base_name}` 디렉터리.
    """
    p = resolve_sanitized_path(sanitized_path)
    return p.parent.parent


def document_type_dir_from_sanitized(sanitized_path: str | Path) -> Path:
    """sanitized 파일 경로로부터 문서 타입 디렉터리(`{document_type}`)를 반환한다.

    구조: `<...>/processed/{document_type}/{version}/...`
    """
    p = resolve_sanitized_path(sanitized_path)
    return p.parent.parent.parent.parent


def components_dir_from_sanitized(sanitized_path: str | Path) -> Path:
    """컴포넌트 디렉터리를 반환(필요 시 생성)한다.

    디렉터리 이름은 베이스 디렉터리(`{base_name}`) 하위의 `_comp` 이다.
    """
    return ensure_dir(base_dir_from_sanitized(sanitized_path) / "_comp")


def meta_path_from_sanitized(sanitized_path: str | Path, basename: str) -> Path:
    """문서 메타데이터 JSON 경로를 반환한다.

    베이스 디렉터리 하위 `_meta/<basename>.json` 경로를 사용하며,
    디렉터리가 없으면 생성한다.

    매개변수:
        sanitized_path: sanitized JSON 경로(절대 또는 상대).
        basename: 원본 문서의 베이스 이름.

    반환값:
        메타데이터 JSON 파일의 절대 경로.
    """
    d = ensure_dir(base_dir_from_sanitized(sanitized_path) / "_meta")
    return d / f"{basename}.json"


def component_paths_from_sanitized(sanitized_path: str | Path, basename: str) -> Dict[str, Path]:
    """컴포넌트 JSON 파일 경로들을 구성한다.

    매개변수:
        sanitized_path: sanitized JSON 경로(절대 또는 상대).
        basename: 출력 파일명의 접두에 사용할 베이스 이름.

    반환값:
        `list`, `table`, `diagram`, `blocks` 키를 가지는 경로 매핑.
    """
    base = components_dir_from_sanitized(sanitized_path)
    return {
        "list":    base / f"{basename}_list_components.json",
        "table":   base / f"{basename}_table_components.json",
        "diagram": base / f"{basename}_diagram_components.json",
        "blocks":  base / f"{basename}_blocks.json",
    }


def docjson_output_path_from_sanitized(sanitized_path: str | Path, basename: str) -> Path:
    """최종 DocJSON 출력 경로를 계산한다.

    규칙: `<processed>/{document_type}/{basename}_{version}.docjson`
    즉, 문서 타입 디렉터리 바로 아래에 `{base_name}_{version}.docjson` 파일로 저장한다.
    """
    version_dir = version_dir_from_sanitized(sanitized_path)
    doc_type_dir = version_dir.parent
    version = version_dir.name
    return doc_type_dir / f"{basename}_{version}.docjson"


def save_json(obj: Any, path: Path) -> Path:
    """객체를 JSON으로 직렬화하여 `path`에 저장한다.

    상위 디렉터리를 생성한 뒤, UTF-8과 들여쓰기를 적용해 저장한다.

    매개변수:
        obj: JSON으로 직렬화 가능한 객체.
        path: 저장 대상 파일 경로.

    반환값:
        저장된 대상 경로(`Path`).
    """
    ensure_dir(path.parent)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_json(path: Path) -> Any:
    """`path`로부터 JSON을 읽어 파싱한다.

    매개변수:
        path: 소스 파일 경로.

    반환값:
        파싱된 파이썬 객체.
    """
    return json.loads(path.read_text(encoding="utf-8"))


def save_list_components_from_sanitized(obj: Dict[str, Any], sanitized_path: str | Path, basename: str) -> Path:
    """리스트 컴포넌트 페이로드를 `_comp`에 저장한다."""
    return save_json(obj, component_paths_from_sanitized(sanitized_path, basename)["list"])


def save_table_components_from_sanitized(obj: Dict[str, Any], sanitized_path: str | Path, basename: str) -> Path:
    """테이블 컴포넌트 페이로드를 `_comp`에 저장한다."""
    return save_json(obj, component_paths_from_sanitized(sanitized_path, basename)["table"])


def save_diagram_components_from_sanitized(obj: Dict[str, Any], sanitized_path: str | Path, basename: str) -> Path:
    """다이어그램 컴포넌트 페이로드를 `_comp`에 저장한다."""
    return save_json(obj, component_paths_from_sanitized(sanitized_path, basename)["diagram"])


def save_blocks_components_from_sanitized(obj: Dict[str, Any], sanitized_path: str | Path, basename: str) -> Path:
    """문서 블록(assembled blocks) 컴포넌트를 `_comp`에 저장한다."""
    return save_json(obj, component_paths_from_sanitized(sanitized_path, basename)["blocks"])


def load_available_components_from_sanitized(sanitized_path: str | Path, basename: str) -> Dict[str, Any]:
    """존재하는 컴포넌트 JSON들을 로드해 합쳐서 반환한다."""
    paths = component_paths_from_sanitized(sanitized_path, basename)
    out: Dict[str, Any] = {}
    if paths["list"].exists():
        lo = load_json(paths["list"])
        out["lists"] = lo.get("lists", [])
        out["consumed"] = lo.get("consumed", [])
    if paths["table"].exists():
        to = load_json(paths["table"])
        out["tables"] = to.get("tables", [])
    if paths["diagram"].exists():
        do = load_json(paths["diagram"])
        out["diagrams"] = do.get("diagrams", do)
    if paths["blocks"].exists():
        bo = load_json(paths["blocks"])
        out["blocks"] = bo.get("blocks", [])
    return out
