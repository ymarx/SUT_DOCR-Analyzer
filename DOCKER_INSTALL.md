폐쇄망 설치(air‑gapped) — WSL2/Linux(amd64)
필수 준비물
- Docker가 설치된 PC
- 사전에 빌드·반출된 이미지 tar: `sut-preprocess_wsl2_1_0.tar`
- 레포지토리 전체(필수) — 개발 모드로만 실행하며, 호스트의 소스 변경을 컨테이너에 즉시 반영합니다.
- 입력 DOCX가 들어있는 `data_store/raw/{document_type}` 디렉터리

설치/로드
- 가장 최근의 sut-preprocess 를 zip하여 로컬 PC에 저장합니다.

중요: .venv 생성 방지(시스템 파이썬 사용)
- 이 이미지는 시스템 파이썬에 패키지가 설치되어 있습니다.
- uv가 `.venv`를 만들지 않도록 다음 원칙을 지키세요.
- 권장: CLI 직접 실행 `sut-preprocess ...` 또는 `uv run --system python ...`만 사용
- 금지/지양: `uv run python ...` (여기서 `--system`이 빠지면 `.venv`가 생성될 수 있음)
- 필요 시 안전장치: 컨테이너 실행/exec 모두 `-e UV_SYSTEM_PYTHON=1`을 지정합니다.

개발 컨테이너 셸 진입(권장)
- 항상 레포지토리를 통째로 마운트하고 작업 디렉터리를 `/app`으로 설정합니다.
- 셸 진입: `docker run --rm -it -v "$PWD":/app -w /app -e UV_SYSTEM_PYTHON=1 --name sutp-dev sut-preprocess:1.0 bash`

컨테이너 내부에서 실행(시스템 파이썬 기반)
- CLI 직접 실행(권장):
  - 단일 파일 처리: `sut-preprocess --raw data_store/raw/gisul-gijun/기술기준_예시.docx --doc-type gisul-gijun --version beta`
  - 디렉터리 전체 처리: `sut-preprocess --raw data_store/raw/gisul-gijun --doc-type gisul-gijun --version beta --all`
  - 디렉터리에서 하나만 처리: `sut-preprocess --raw data_store/raw/gisul-gijun --doc-type gisul-gijun --version beta --one 기술기준_예시.docx`
- 또는 uv 시스템 모드로 실행:
  - 단일 파일 처리: `uv run --system python src/mypkg/cli/main.py --raw data_store/raw/gisul-gijun/기술기준_예시.docx --doc-type gisul-gijun --version beta`
  - 디렉터리 전체 처리: `uv run --system python src/mypkg/cli/main.py --raw data_store/raw/gisul-gijun --doc-type gisul-gijun --version beta --all`
  - 디렉터리에서 하나만 처리: `uv run --system python src/mypkg/cli/main.py --raw data_store/raw/gisul-gijun --doc-type gisul-gijun --version beta --one 기술기준_예시.docx`

산출물 경로 규칙
- 최종 DocJSON: `data_store/processed/{document_type}/{base_name}_{version}.docjson`
- 컴포넌트: `data_store/processed/{document_type}/{version}/{base_name}/_comp/*`
- 메타: `data_store/processed/{document_type}/{version}/{base_name}/_meta/{base_name}.json`

