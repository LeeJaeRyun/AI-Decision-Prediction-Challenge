# LLM Agent Tool-Action 예측 평가 MVP

사용자 한국어 지시문과 사용 가능한 Tool 목록을 입력으로 받아, 다음에 호출해야 할 Tool-Action JSON을 예측하고 평가하는 MVP입니다.

이 프로젝트는 LLM을 새로 학습하지 않습니다. 실제 이메일, 캘린더, 슬랙, 파일, 웹 검색도 실행하지 않습니다. 모델 또는 baseline은 실행할 행동을 나타내는 JSON만 생성하고, `evaluate.py`가 실제 `predictions.jsonl` 파일을 읽어 지표를 계산합니다.

## 설치 방법

```bash
cd tool_action_mvp
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

macOS/Linux에서는 가상환경 활성화 명령만 다릅니다.

```bash
source .venv/bin/activate
```

## .env 설정

OpenAI 또는 Gemini 예측을 실행하려면 `.env.example`을 참고해 `.env` 파일을 만듭니다.

```bash
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```

`OPENAI_MODEL`과 `GEMINI_MODEL`은 생략할 수 있습니다. 생략하면 각 예측 스크립트의 기본 모델을 사용합니다.

## 실행 순서

### 1. Random baseline 실행 및 평가

```bash
python src/baselines.py --tools tools.json --data data/test_data.jsonl --method random --output outputs/predictions_random.jsonl
python src/evaluate.py --tools tools.json --predictions outputs/predictions_random.jsonl --output outputs/evaluation_random.json --detail outputs/evaluation_detail_random.csv
```

### 2. Keyword baseline 실행 및 평가

```bash
python src/baselines.py --tools tools.json --data data/test_data.jsonl --method keyword --output outputs/predictions_keyword.jsonl
python src/evaluate.py --tools tools.json --predictions outputs/predictions_keyword.jsonl --output outputs/evaluation_keyword.json --detail outputs/evaluation_detail_keyword.csv
```

### 3. OpenAI 예측 실행 및 평가

API 비용을 줄이기 위해 `--limit`으로 처리 개수를 제한할 수 있습니다.

```bash
python src/predict_openai.py --tools tools.json --data data/test_data.jsonl --output outputs/predictions_openai.jsonl --limit 50
python src/evaluate.py --tools tools.json --predictions outputs/predictions_openai.jsonl --output outputs/evaluation_openai.json --detail outputs/evaluation_detail_openai.csv
```

### 4. Gemini 예측 실행 및 평가

Gemini API 키를 쓰려면 `GEMINI_API_KEY`를 설정한 뒤 아래 명령을 실행합니다. 출력 포맷은 OpenAI 예측과 같으므로 `evaluate.py`를 그대로 사용합니다.

```bash
python src/predict_gemini.py --tools tools.json --data data/test_data.jsonl --output outputs/predictions_gemini.jsonl --limit 50
python src/evaluate.py --tools tools.json --predictions outputs/predictions_gemini.jsonl --output outputs/evaluation_gemini.json --detail outputs/evaluation_detail_gemini.csv
```

무료 티어에서 분당 요청 제한에 걸리면 요청 사이에 대기 시간을 줄 수 있습니다.

```bash
python src/predict_gemini.py --tools tools.json --data data/test_data.jsonl --output outputs/predictions_gemini.jsonl --limit 50 --delay-seconds 13
```

API 호출 실패나 JSON 파싱 실패가 발생해도 전체 실행은 중단되지 않고, 해당 샘플의 `error` 필드에 이유를 기록합니다.

### 5. 결과표 생성

OpenAI와 Gemini 결과가 모두 있을 때:

```bash
python src/make_result_table.py --inputs outputs/evaluation_random.json outputs/evaluation_keyword.json outputs/evaluation_openai.json outputs/evaluation_gemini.json --names Random Keyword OpenAI Gemini --output outputs/result_table.csv
```

API 결과가 아직 없다면 Random과 Keyword만 넣어 결과표를 만들 수 있습니다.

```bash
python src/make_result_table.py --inputs outputs/evaluation_random.json outputs/evaluation_keyword.json --names Random Keyword --output outputs/result_table.csv
```

## 평가 지표

- `tool_accuracy`: 예측한 `tool_name`이 정답과 같은 비율
- `argument_f1`: `arguments`의 key-value 쌍을 기준으로 계산한 샘플별 F1 평균
- `exact_match`: `tool_name`과 `arguments`가 모두 정확히 같은 비율
- `json_success_rate`: 예측 JSON 생성 또는 파싱이 성공한 비율
- `hallucinated_tool_rate`: 예측한 `tool_name`이 `tools.json`에 없는 비율
- `avg_latency_ms`: 예측 파일에 기록된 평균 지연 시간

추가 보조 지표:

- `normalized_argument_f1`: `"14:00"`과 `"오후 2시"`처럼 의미가 같은 시간 표현을 정규화한 뒤 계산한 Argument F1
- `normalized_exact_match`: `tool_name`과 정규화된 `arguments`가 모두 같은 비율

기본 `argument_f1`과 `exact_match`는 문자열 완전일치 기준이므로 보수적인 점수입니다. 보고서에서는 기본 지표와 정규화 지표를 함께 제시하면, 자동 채점의 엄격함과 실제 의미적 예측 품질을 같이 설명할 수 있습니다.

## 결과보고서 문장 예시

본 실험은 한국어 사용자 지시문 50개와 12개 Tool 정의를 사용해 Tool-Action 예측 성능을 비교했다. Random baseline, Keyword baseline, OpenAI 기반 예측, Gemini 기반 예측은 동일한 `evaluate.py`로 평가했으며, 결과표의 모든 수치는 저장된 `predictions.jsonl` 파일에서 계산했다. 따라서 보고서의 Tool Accuracy, Argument F1, Exact Match, JSON Success Rate 값은 임의 입력값이 아니라 재현 가능한 평가 스크립트의 산출물이다.

## 멀티모달 이미지/음성 확장

`predict_gemini.py`는 텍스트 지시문뿐 아니라 JSONL 샘플의 `image_path`, `audio_path`, `image_paths`, `audio_paths` 필드를 읽어 Gemini에 실제 이미지/오디오 바이너리를 함께 전달한다. 상대 경로는 데이터 파일이 있는 `data/` 디렉터리를 기준으로 해석한다.

발표용 멀티모달 샘플 자산 생성:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\generate_multimodal_assets.ps1
```

멀티모달 예측 및 평가:

```bash
python src/predict_gemini.py --tools tools.json --data data/multimodal_test_data.jsonl --output outputs/predictions_gemini_multimodal.jsonl
python src/evaluate.py --tools tools.json --predictions outputs/predictions_gemini_multimodal.jsonl --output outputs/evaluation_gemini_multimodal.json --detail outputs/evaluation_detail_gemini_multimodal.csv
```

로컬 인증서 문제로 Gemini 호출이 실패하면 다음처럼 실행할 수 있다.

```powershell
$env:GEMINI_ALLOW_INSECURE_SSL='1'; python src\predict_gemini.py --tools tools.json --data data\multimodal_test_data.jsonl --output outputs\predictions_gemini_multimodal.jsonl
```

현재 멀티모달 샘플은 이미지 3개, 음성 2개로 구성되어 있으며, `Gemini-MM` 결과는 `outputs/result_table.csv`에 포함된다.
