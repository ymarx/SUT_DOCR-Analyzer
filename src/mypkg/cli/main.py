
# mypkg/cli/main.py
# 디렉터리 구조 규칙 (자세한 사용 예시는 README.md 참고)

from __future__ import annotations
import argparse, sys, json
from pathlib import Path
from mypkg.pipelines.layout_analyzer_pipeline import run_pipeline
from mypkg.core.docjson_types import DocumentDocJSON
from mypkg.core.io import (
    docjson_output_path_from_sanitized,
    resolve_sanitized_path,
    base_dir_from_sanitized,
    component_paths_from_sanitized,
    load_available_components_from_sanitized,
    meta_path_from_sanitized,
    load_json,
)
from mypkg.pipelines.docx_parsing_pipeline import DocxParsingPipeline

def parse_args():
    ap = argparse.ArgumentParser(description="Raw DOCX → Sanitized → Components → DocJSON | 또는 중간 산출물(inspect) 확인")
    # 실행 모드 공용 옵션 (run/inspect에서 일부만 사용)
    # 입력: 파일 또는 디렉터리(data_store/raw/{document_type}) — run 모드에서만 필수
    ap.add_argument("--raw", help="원시 DOCX 파일 경로 또는 디렉터리 경로(data_store/raw/{document_type})")
    ap.add_argument("--doc-type", help="문서 타입(ex. gisul-gijun)")
    ap.add_argument("--version", help="버전(ex. v3)")
    ap.add_argument("--processed-root", default="./data_store/processed", help="processed 루트 디렉터리 (기본: ./data_store/processed)")
    # 출력 설정(파일 경로 또는 디렉터리). 단일 파일 처리 시에만 의미 있음.
    ap.add_argument("--out", help="출력 DocJSON 경로(파일 또는 부모 디렉터리). 디렉터리 처리 시 자동 경로 사용")
    # 디렉터리 처리 모드: 전체 또는 하나 선택(비대화식)
    grp = ap.add_mutually_exclusive_group()
    grp.add_argument("--all", action="store_true", help="디렉터리 입력 시 모든 DOCX 처리")
    grp.add_argument("--one", help="디렉터리 입력 시 하나만 처리(파일명 또는 경로). 예: sample1.docx 또는 하위경로/sample1.docx")
    # 분석 동작 옵션
    ap.add_argument("--no-emit", action="store_true", help="컴포넌트 파일 생성 생략")
    ap.add_argument("--no-use", action="store_true", help="기존 컴포넌트 미사용, 즉석 분석")

    # Inspect 모드(중간 산출물 조회) 옵션
    ap.add_argument("--inspect", choices=[
        "sanitized", "comp", "meta", "blocks", "lists", "tables", "diagrams", "all", "ls"
    ], help="중간 산출물 확인 모드")
    ap.add_argument("--sanitized", help="sanitized JSON 경로(예: .../_sanitized/<name>_sanitized.json)")
    ap.add_argument("--base-dir", help="처리 베이스 디렉터리 경로(예: .../processed/{doc_type}/{version}/{base_name}) — sanitized를 자동 추정")
    ap.add_argument("--json", action="store_true", help="요약 대신 원본 JSON을 stdout으로 출력")
    return ap.parse_args()

def _resolve_one_from_dir(dir_path: Path, hint: str) -> Path | None:
    """디렉터리 내부에서 hint로 지정된 하나의 .docx를 찾아 Path 반환.
    - hint가 절대/상대 경로면 그대로 사용(존재 검증)
    - hint가 파일명 또는 stem이면 디렉터리 내에서 검색
    """
    cand = Path(hint)
    if cand.is_file():
        return cand.resolve()
    cand2 = (dir_path / hint)
    if cand2.is_file():
        return cand2.resolve()
    # 파일명 일치
    matches = [p for p in dir_path.rglob("*.docx") if p.name == hint]
    if len(matches) == 1:
        return matches[0].resolve()
    # stem 일치
    matches = [p for p in dir_path.rglob("*.docx") if p.stem == hint]
    if len(matches) == 1:
        return matches[0].resolve()
    return None


def _find_sanitized_from_base_dir(base_dir: Path) -> Path | None:
    sd = base_dir / "_sanitized"
    if not sd.is_dir():
        return None
    cands = [p for p in sd.glob("*_sanitized.json")]
    if not cands:
        # 다른 이름의 sanitized가 있을 수도 있으니 폴백으로 .json 전체 확인
        cands = [p for p in sd.glob("*.json")]
    if not cands:
        return None
    # 최신 수정 시각 우선
    cands.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return cands[0].resolve()


def _print_path_exists(label: str, p: Path):
    print(f"{label}: {'exists' if p.exists() else 'missing'}  {p}")


def _inspect(a) -> int:
    # sanitized 경로 결정
    san_path: Path | None = None
    if a.sanitized:
        san_path = resolve_sanitized_path(a.sanitized)
    elif a.base_dir:
        cand = _find_sanitized_from_base_dir(Path(a.base_dir).resolve())
        if cand:
            san_path = cand
    if san_path is None:
        print("error: --inspect 모드에서는 --sanitized 또는 --base-dir 중 하나를 지정해야 합니다.", file=sys.stderr)
        return 2

    san_path = san_path.resolve()
    base_name = base_dir_from_sanitized(san_path).name

    # 경로들 구성
    paths = component_paths_from_sanitized(san_path, base_name)
    meta_p = meta_path_from_sanitized(san_path, base_name)
    docjson_p = docjson_output_path_from_sanitized(san_path, base_name)

    if a.inspect == "ls":
        _print_path_exists("sanitized", san_path)
        _print_path_exists("comp.list", paths["list"])
        _print_path_exists("comp.table", paths["table"])
        _print_path_exists("comp.diagram", paths["diagram"])
        _print_path_exists("comp.blocks", paths["blocks"])
        _print_path_exists("meta", meta_p)
        _print_path_exists("docjson", docjson_p)
        return 0

    if a.inspect in {"sanitized", "all"}:
        ir = load_json(san_path)
        if a.json:
            print(json.dumps(ir, ensure_ascii=False, indent=2))
        else:
            paras = len(ir.get("paragraphs", []) if isinstance(ir, dict) else [])
            tbls = len(ir.get("tables", []) if isinstance(ir, dict) else [])
            drws = len(ir.get("drawings", []) if isinstance(ir, dict) else [])
            hdrs = len(ir.get("headers", []) if isinstance(ir, dict) else [])
            ftrs = len(ir.get("footers", []) if isinstance(ir, dict) else [])
            print(f"sanitized: paragraphs={paras} tables={tbls} drawings={drws} headers={hdrs} footers={ftrs}")

    comps = load_available_components_from_sanitized(san_path, base_name)
    if a.inspect in {"comp", "all", "lists", "tables", "diagrams", "blocks"}:
        if a.inspect in {"comp", "all"} and not a.json:
            print("components present:", ", ".join(sorted([k for k in comps.keys()])))
        if a.inspect in {"lists"} or (a.inspect == "all"):
            ls = comps.get("lists", [])
            if a.json:
                print(json.dumps({"lists": ls}, ensure_ascii=False, indent=2))
            else:
                print(f"lists: {len(ls)} items, consumed={len(comps.get('consumed', []))}")
        if a.inspect in {"tables"} or (a.inspect == "all"):
            ts = comps.get("tables", [])
            if a.json:
                print(json.dumps({"tables": ts}, ensure_ascii=False, indent=2))
            else:
                print(f"tables: {len(ts)} blocks")
        if a.inspect in {"diagrams"} or (a.inspect == "all"):
            ds = comps.get("diagrams", [])
            if a.json:
                print(json.dumps({"diagrams": ds}, ensure_ascii=False, indent=2))
            else:
                print(f"diagrams: {len(ds)} blocks")
        if a.inspect in {"blocks"} or (a.inspect == "all"):
            bs = comps.get("blocks", [])
            if a.json:
                print(json.dumps({"blocks": bs}, ensure_ascii=False, indent=2))
            else:
                print(f"blocks: {len(bs)} total")

    if a.inspect in {"meta", "all"}:
        if meta_p.exists():
            md = load_json(meta_p)
            if a.json:
                print(json.dumps({"metadata": md}, ensure_ascii=False, indent=2))
            else:
                keys = [k for k,v in md.items() if v]
                print("meta:", ", ".join(keys))
        else:
            print(f"meta: missing ({meta_p})")
    return 0


def main():
    a = parse_args()

    # Inspect 모드 우선 처리 (run과 독립)
    if a.inspect:
        return _inspect(a)

    # 이하 run 모드
    # 필수 인자 검증
    missing = []
    if not a.raw: missing.append("--raw")
    if not a.doc_type: missing.append("--doc-type")
    if not a.version: missing.append("--version")
    if missing:
        print("error: run 모드 필수 인자 누락: " + ", ".join(missing), file=sys.stderr)
        return 2

    processed_root = Path(a.processed_root).resolve()
    raw_path = Path(a.raw).resolve()
    if not raw_path.exists():
        print(f"error: 입력 경로가 존재하지 않습니다: {raw_path}", file=sys.stderr)
        return 2

    import asyncio
    parser_pipeline = DocxParsingPipeline()

    def _run_one(docx_file: Path):
        base_name = docx_file.stem
        base_dir = processed_root / a.doc_type / a.version / base_name
        res = asyncio.run(parser_pipeline.run(docx_file, base_dir))
        sanitized_path: Path = Path(res["sanitized_output"]).resolve()  # type: ignore[index]
        # out이 지정된 경우(단일 파일 처리 시만 사용). 디렉터리 처리에서 --one인 경우에도 허용
        if a.out and (raw_path.is_file() or a.one):
            out_target = Path(a.out).resolve()
        else:
            out_target = docjson_output_path_from_sanitized(sanitized_path, base_name)
        docjson = run_pipeline(
            sanitized_path=sanitized_path,
            out_docjson_path=out_target,
            emit_components=(not a.no_emit),
            use_components=(not a.no_use),
            doc_version=a.version,
        )
        sections = len(docjson.sections)
        blocks = len(docjson.blocks)
        final_path = out_target if out_target.suffix else docjson_output_path_from_sanitized(resolve_sanitized_path(sanitized_path), base_name)
        print(f"[ok] wrote: {final_path}  sections={sections} blocks={blocks}")

    if raw_path.is_dir():
        # 디렉터리 내 모든 .docx 수집(~$, 임시 파일 제외)
        candidates = [p for p in raw_path.rglob("*.docx") if p.is_file() and not p.name.startswith("~$")]
        if not candidates:
            print(f"warn: DOCX 파일을 찾지 못했습니다: {raw_path}")
            return 0
        if a.all:
            for docx_file in sorted(candidates):
                _run_one(docx_file)
            return 0
        if a.one:
            picked = _resolve_one_from_dir(raw_path, a.one)
            if not picked:
                print(f"error: --one 으로 지정한 파일을 찾지 못했습니다: {a.one}", file=sys.stderr)
                return 2
            _run_one(picked)
            return 0
        print("error: 디렉터리 입력 시 --all 또는 --one <파일> 중 하나를 지정해야 합니다.", file=sys.stderr)
        return 2
    else:
        if raw_path.suffix.lower() != ".docx":
            print(f"error: DOCX 파일이 아닙니다: {raw_path}", file=sys.stderr)
            return 2
        _run_one(raw_path)
        return 0

def entry_point():
    """콘솔 스크립트 진입점. setuptools의 [project.scripts]와 호환을 위해 제공."""
    return main()

if __name__ == "__main__":
    sys.exit(main())
