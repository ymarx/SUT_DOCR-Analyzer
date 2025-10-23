"""
코드 정합성 및 구조 검증 스크립트

GPU 없이도 import, 구조, 타입 힌트 등을 검증합니다.
"""

import sys
import ast
import importlib.util
from pathlib import Path
from typing import List, Dict, Tuple


class CodeValidator:
    """코드 검증 클래스"""

    def __init__(self, src_dir: Path):
        self.src_dir = src_dir
        self.errors = []
        self.warnings = []
        self.success_count = 0

    def validate_all(self) -> Tuple[int, int, int]:
        """모든 검증 실행"""
        print("="*70)
        print("DeepSeek-OCR 코드 정합성 검증")
        print("="*70)

        # 1. Python 파일 찾기
        py_files = list(self.src_dir.rglob("*.py"))
        print(f"\n[1/4] Python 파일 검색: {len(py_files)}개 발견")

        # 2. Import 검증
        print(f"\n[2/4] Import 구문 검증...")
        self._validate_imports(py_files)

        # 3. 구조 검증
        print(f"\n[3/4] 코드 구조 검증...")
        self._validate_structure(py_files)

        # 4. 타입 힌트 검증
        print(f"\n[4/4] 타입 힌트 검증...")
        self._validate_type_hints(py_files)

        return self.success_count, len(self.warnings), len(self.errors)

    def _validate_imports(self, py_files: List[Path]):
        """Import 구문 검증"""
        for py_file in py_files:
            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()

                tree = ast.parse(content, filename=str(py_file))

                # Import 분석
                imports = []
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imports.append(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            imports.append(node.module)

                # 상대 경로 확인
                relative_path = py_file.relative_to(self.src_dir.parent)
                print(f"  ✅ {relative_path}: {len(imports)} imports")
                self.success_count += 1

            except SyntaxError as e:
                self.errors.append(f"{py_file}: Syntax error - {e}")
                print(f"  ❌ {py_file}: Syntax error")
            except Exception as e:
                self.warnings.append(f"{py_file}: {e}")

    def _validate_structure(self, py_files: List[Path]):
        """코드 구조 검증"""
        for py_file in py_files:
            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()

                tree = ast.parse(content, filename=str(py_file))

                # 클래스와 함수 개수
                classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
                functions = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]

                relative_path = py_file.relative_to(self.src_dir.parent)

                if len(classes) > 0 or len(functions) > 0:
                    print(f"  ✅ {relative_path}: {len(classes)} classes, {len(functions)} functions")
                else:
                    print(f"  ⚠️  {relative_path}: Empty module")
                    self.warnings.append(f"{py_file}: Empty module (no classes/functions)")

            except Exception as e:
                self.errors.append(f"{py_file}: Structure validation failed - {e}")

    def _validate_type_hints(self, py_files: List[Path]):
        """타입 힌트 검증"""
        for py_file in py_files:
            # __init__.py는 스킵
            if py_file.name == "__init__.py":
                continue

            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()

                tree = ast.parse(content, filename=str(py_file))

                # 함수의 타입 힌트 확인
                functions = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
                typed_functions = 0

                for func in functions:
                    # Private 함수는 스킵
                    if func.name.startswith("_"):
                        continue

                    # 반환 타입 힌트가 있는지 확인
                    if func.returns is not None:
                        typed_functions += 1

                relative_path = py_file.relative_to(self.src_dir.parent)

                if functions:
                    coverage = (typed_functions / len(functions)) * 100 if functions else 0
                    if coverage >= 50:
                        print(f"  ✅ {relative_path}: {coverage:.0f}% typed")
                    else:
                        print(f"  ⚠️  {relative_path}: {coverage:.0f}% typed (권장: 50%+)")
                        self.warnings.append(f"{py_file}: Low type hint coverage ({coverage:.0f}%)")

            except Exception as e:
                self.errors.append(f"{py_file}: Type hint validation failed - {e}")

    def print_summary(self):
        """검증 결과 요약 출력"""
        print("\n" + "="*70)
        print("검증 결과 요약")
        print("="*70)
        print(f"✅ 성공: {self.success_count}")
        print(f"⚠️  경고: {len(self.warnings)}")
        print(f"❌ 에러: {len(self.errors)}")

        if self.warnings:
            print(f"\n⚠️  경고 목록 (상위 5개):")
            for warning in self.warnings[:5]:
                print(f"  - {warning}")

        if self.errors:
            print(f"\n❌ 에러 목록:")
            for error in self.errors:
                print(f"  - {error}")

        if not self.errors:
            print(f"\n✅ 모든 검증 통과!")
            return 0
        else:
            print(f"\n❌ {len(self.errors)}개 에러 발생")
            return 1


def validate_module_dependencies():
    """모듈 간 의존성 검증"""
    print("\n" + "="*70)
    print("모듈 의존성 검증")
    print("="*70)

    required_modules = {
        "core": ["types.py", "config.py", "utils.py"],
        "engine": ["deepseek_engine.py", "prompts.py"],
        "pipeline": ["pdf_parser.py", "structure_analyzer.py", "element_analyzer.py", "text_enricher.py"],
        "cli": ["main.py"],
    }

    src_dir = Path("src/deepseek_ocr")
    all_ok = True

    for module, files in required_modules.items():
        module_path = src_dir / module
        if not module_path.exists():
            print(f"❌ 모듈 없음: {module}")
            all_ok = False
            continue

        print(f"\n[{module}]")
        for file in files:
            file_path = module_path / file
            if file_path.exists():
                size = file_path.stat().st_size
                print(f"  ✅ {file}: {size} bytes")
            else:
                print(f"  ❌ {file}: 파일 없음")
                all_ok = False

    if all_ok:
        print(f"\n✅ 모든 필수 모듈 존재")
        return 0
    else:
        print(f"\n❌ 일부 모듈 누락")
        return 1


def validate_configs():
    """설정 파일 검증"""
    print("\n" + "="*70)
    print("설정 파일 검증")
    print("="*70)

    # runpod 스크립트 확인
    runpod_files = ["setup.sh", "process.py", "README.md"]
    runpod_dir = Path("runpod")

    print("\n[RunPod 배포 스크립트]")
    for file in runpod_files:
        file_path = runpod_dir / file
        if file_path.exists():
            print(f"  ✅ {file}")
        else:
            print(f"  ❌ {file}: 파일 없음")

    # 테스트 스크립트 확인
    test_files = ["test_integration.py"]
    tests_dir = Path("tests")

    print("\n[테스트 스크립트]")
    for file in test_files:
        file_path = tests_dir / file
        if file_path.exists():
            print(f"  ✅ {file}")
        else:
            print(f"  ❌ {file}: 파일 없음")

    # 문서 확인
    doc_files = ["README.md", "PROJECT_COMPLETE.md", "IMPLEMENTATION_COMPLETE.md"]

    print("\n[문서 파일]")
    for file in doc_files:
        file_path = Path(file)
        if file_path.exists():
            print(f"  ✅ {file}")
        else:
            print(f"  ⚠️  {file}: 파일 없음")

    return 0


def main():
    """메인 실행"""
    print("\n🔍 DeepSeek-OCR 프로젝트 코드 검증 시작\n")

    # 작업 디렉토리 확인
    if not Path("src/deepseek_ocr").exists():
        print("❌ src/deepseek_ocr 디렉토리를 찾을 수 없습니다.")
        print("프로젝트 루트에서 실행해주세요.")
        return 1

    # 1. 모듈 의존성 검증
    exit_code = validate_module_dependencies()

    # 2. 코드 검증
    validator = CodeValidator(Path("src/deepseek_ocr"))
    success, warnings, errors = validator.validate_all()
    validator.print_summary()
    exit_code = max(exit_code, validator.print_summary())

    # 3. 설정 파일 검증
    exit_code = max(exit_code, validate_configs())

    # 최종 요약
    print("\n" + "="*70)
    print("전체 검증 완료")
    print("="*70)

    if exit_code == 0:
        print("✅ 모든 검증 통과! 코드가 정상적으로 구조화되어 있습니다.")
        print("\n다음 단계:")
        print("  1. GPU 환경에서 실제 테스트 실행")
        print("  2. RunPod 배포 및 실전 문서 처리")
    else:
        print("⚠️  일부 경고 또는 에러가 발생했습니다.")
        print("위 내용을 검토하고 필요시 수정해주세요.")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
