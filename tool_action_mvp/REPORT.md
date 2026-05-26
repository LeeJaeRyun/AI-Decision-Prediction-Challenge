# 멀티모달 컨텍스트 기반 LLM Agent 차기 행동 의사결정 예측 결과 보고서

## 1. 프로젝트 개요

본 프로젝트는 **멀티모달 컨텍스트 기반 LLM Agent의 차기 행동 의사결정 예측**을 목표로 한다. 사용자의 지시문, 이미지, 음성 등 다양한 컨텍스트와 사용 가능한 Tool 목록이 주어졌을 때, LLM Agent가 다음 단계에서 호출해야 할 Tool과 arguments를 구조화된 JSON으로 예측한다.

예를 들어 사용자가 "이미지에 보이는 회의 정보를 캘린더에 추가해줘"라고 요청하고, 이미지 안에 다음 정보가 보인다고 가정한다.

```text
Title: Product Sync
Date: Tomorrow
Time: 14:00
Location: Zoom
```

Agent는 실제 캘린더를 실행하는 것이 아니라 다음과 같은 행동 계획 JSON을 출력해야 한다.

```json
{
  "tool_name": "calendar.create_event",
  "arguments": {
    "title": "Product Sync",
    "date": "Tomorrow",
    "time": "14:00"
  }
}
```

본 프로젝트의 핵심은 **LLM이 외부 업무를 직접 실행하지 않고, 실행 직전 단계의 행동 의사결정을 예측하게 하는 것**이다. 따라서 이메일 전송, 캘린더 등록, 슬랙 메시지 전송 등 실제 외부 서비스 호출은 수행하지 않는다. 대신 예측 결과를 정답 `gold_action`과 비교하여 Tool 선택 정확도와 인자 추출 성능을 평가한다.

## 2. 주제 적합성

AI Agent는 일반 챗봇과 달리 사용자 목적을 달성하기 위해 외부 Tool을 선택하고 호출한다. 이 과정에서 핵심적인 의사결정은 다음 두 가지다.

- 어떤 Tool을 호출할 것인가
- 해당 Tool에 어떤 arguments를 전달할 것인가

잘못된 Tool을 선택하거나 잘못된 arguments를 생성하면 실제 서비스에서는 잘못된 메일 발송, 잘못된 일정 등록, 잘못된 검색 수행으로 이어질 수 있다. 따라서 Agent의 다음 행동을 미리 예측하고 평가하는 것은 Agent 시스템의 안전성과 신뢰성을 높이기 위한 중요한 문제다.

본 프로젝트는 초기 텍스트 기반 Tool-Action 예측 파이프라인을 구현한 뒤, 이미지와 음성 컨텍스트를 추가하여 멀티모달 입력에서도 동일한 행동 예측 구조가 동작하도록 확장했다. 최종적으로 텍스트, 이미지, 음성을 모두 입력 컨텍스트로 사용할 수 있는 Agent 행동 의사결정 예측 파이프라인을 구성했다.

## 3. 문제 정의

### 3.1 입력

각 샘플은 다음 정보를 포함한다.

- 사용자 instruction
- 사용 가능한 Tool 목록
- 선택적으로 제공되는 이미지 파일 경로
- 선택적으로 제공되는 음성 파일 경로
- 정답 행동 JSON인 `gold_action`

멀티모달 샘플 형식은 다음과 같다.

```json
{
  "id": 101,
  "instruction": "이미지에 보이는 회의 정보를 캘린더에 추가해줘.",
  "image_path": "media/meeting_notice.png",
  "gold_action": {
    "tool_name": "calendar.create_event",
    "arguments": {
      "title": "Product Sync",
      "date": "Tomorrow",
      "time": "14:00"
    }
  }
}
```

음성 샘플은 `audio_path` 필드를 사용한다.

```json
{
  "id": 103,
  "instruction": "오디오에서 말한 요청을 다음 Agent 행동 JSON으로 바꿔줘.",
  "audio_path": "media/email_instruction.wav",
  "gold_action": {
    "tool_name": "email.send",
    "arguments": {
      "recipient": "Professor Kim",
      "subject": "Assignment submission",
      "body": "I have submitted the report."
    }
  }
}
```

### 3.2 출력

모델은 다음 형식의 JSON 객체 하나만 출력해야 한다.

```json
{
  "tool_name": "string",
  "arguments": {
    "key": "value"
  }
}
```

예측 결과는 `pred_action`으로 저장하고, 정답 `gold_action`과 비교하여 평가한다.

## 4. Tool 정의

`tools.json`에는 총 12개의 Tool을 정의했다.

| Tool | 목적 |
|---|---|
| `calendar.create_event` | 새로운 캘린더 일정 생성 |
| `calendar.update_event` | 기존 캘린더 일정 수정 |
| `weather.search` | 특정 지역과 날짜의 날씨 조회 |
| `email.send` | 이메일 전송 |
| `slack.send_message` | 슬랙 메시지 전송 |
| `reminder.create` | 리마인더 생성 |
| `web.search` | 웹 검색 |
| `file.create_document` | 문서 생성 |
| `todo.create_task` | 할 일 추가 |
| `map.search_place` | 장소 검색 |
| `translate.text` | 번역 |
| `calculator.calculate` | 계산 |

각 Tool은 `tool_name`, `description`, `parameters`를 가진다. 모델은 Tool 이름만 보고 선택하는 것이 아니라, Tool 설명과 parameter 정보를 함께 참고하여 다음 행동을 결정한다.

## 5. 데이터 구성

### 5.1 텍스트 기반 데이터

기본 평가 데이터는 한국어 사용자 지시문을 중심으로 구성했다. 각 샘플은 사용자의 자연어 요청과 정답 Tool-Action JSON을 포함한다. 예시는 다음과 같다.

```json
{
  "instruction": "내일 오후 2시에 팀 회의 일정 잡아줘.",
  "gold_action": {
    "tool_name": "calendar.create_event",
    "arguments": {
      "title": "팀 회의",
      "date": "내일",
      "time": "14:00"
    }
  }
}
```

텍스트 평가에는 총 19개 샘플을 사용했다. 캘린더, 날씨, 이메일, 웹 검색, 할 일 등 여러 Tool을 포함하여 Tool 선택과 argument 추출을 함께 평가했다.

### 5.2 멀티모달 데이터

멀티모달 평가 데이터는 총 5개 샘플로 구성했다.

| 유형 | 샘플 수 | 설명 |
|---|---:|---|
| 이미지 | 3 | 회의 공지 이미지, 날씨 카드 이미지 |
| 음성 | 2 | 이메일 전송 요청, 슬랙 메시지 전송 요청 |

이미지와 음성 파일은 `data/media/`에 저장했다.

| 파일 | 역할 |
|---|---|
| `meeting_notice.png` | 회의 제목, 날짜, 시간 정보를 담은 이미지 |
| `weather_card.png` | 위치와 날짜를 담은 날씨 카드 이미지 |
| `email_instruction.wav` | 이메일 전송 요청 음성 |
| `slack_instruction.wav` | 슬랙 메시지 전송 요청 음성 |

이 데이터는 단순히 파일 경로만 저장한 것이 아니라, `predict_gemini.py`에서 실제 이미지와 음성 파일을 읽어 Gemini API의 멀티모달 입력으로 전달한다.

## 6. 모델 및 구현 방식

### 6.1 전체 파이프라인

구현 흐름은 다음과 같다.

```text
사용자 instruction
 + 선택적 이미지/음성 컨텍스트
 + Tool 목록
        ↓
LLM 기반 Tool-Action 예측
        ↓
pred_action JSON 생성
        ↓
gold_action과 비교 평가
        ↓
평가 지표 및 상세 CSV 저장
```

### 6.2 비교 방법

성능 비교를 위해 다음 방법을 사용했다.

| 방법 | 설명 |
|---|---|
| Random | 사용 가능한 Tool 중 하나를 무작위 선택 |
| Keyword | instruction의 키워드를 규칙 기반으로 매칭 |
| Gemini | 텍스트 instruction 기반 LLM 예측 |
| Gemini-MM | 이미지/음성 컨텍스트를 포함한 Gemini 멀티모달 예측 |

Random baseline은 최소 기준선 역할을 한다. Keyword baseline은 간단한 규칙 기반 접근이 어느 정도까지 동작하는지 확인하기 위한 비교군이다. Gemini는 LLM 기반 Tool-Action 예측 성능을 보기 위한 방법이고, Gemini-MM은 이미지와 음성 컨텍스트까지 포함한 최종 멀티모달 방법이다.

### 6.3 멀티모달 입력 처리

`predict_gemini.py`는 각 샘플에서 다음 필드를 읽는다.

- `image_path`
- `audio_path`
- `image_paths`
- `audio_paths`

상대 경로는 데이터 파일이 위치한 `data/` 디렉터리를 기준으로 해석한다. 파일은 base64로 인코딩한 뒤 Gemini `inlineData` 형식으로 전달한다. MIME type은 파일 확장자를 기준으로 `image/png`, `audio/wav` 등으로 설정한다.

따라서 본 프로젝트의 멀티모달 예측은 OCR 결과나 음성 전사 텍스트를 미리 넣는 방식이 아니라, 이미지와 음성 파일 자체를 모델 입력에 포함하는 방식이다.

## 7. 평가 지표

평가에는 다음 지표를 사용했다.

| 지표 | 설명 |
|---|---|
| `tool_accuracy` | 예측한 `tool_name`이 정답과 같은 비율 |
| `argument_f1` | arguments의 key-value 쌍 기준 F1 평균 |
| `normalized_argument_f1` | 시간 표현 등을 정규화한 뒤 계산한 Argument F1 |
| `exact_match` | Tool 이름과 arguments가 모두 정확히 같은 비율 |
| `normalized_exact_match` | 정규화된 arguments 기준 Exact Match |
| `json_success_rate` | 예측 JSON 생성 또는 파싱 성공 비율 |
| `hallucinated_tool_rate` | 존재하지 않는 Tool을 예측한 비율 |
| `avg_latency_ms` | 평균 응답 지연 시간 |

`exact_match`는 매우 엄격한 지표다. 예를 들어 `"14:00"`과 `"오후 2시"`는 의미가 같지만 문자열이 다르므로 strict 기준에서는 오답 처리된다. 이를 보완하기 위해 시간 표현 정규화를 반영한 normalized 지표를 함께 계산했다.

## 8. 실험 결과

최종 결과표는 `outputs/result_table.csv`에 저장했다.

| Method | Total | Tool Accuracy | Argument F1 | Normalized Argument F1 | Exact Match | Normalized Exact Match | JSON Success Rate | Hallucinated Tool Rate | Avg Latency ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Random | 19 | 0.1579 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 0.0000 | 0.00 |
| Keyword | 19 | 0.9474 | 0.4140 | 0.4140 | 0.1579 | 0.1579 | 1.0000 | 0.0000 | 0.00 |
| Gemini | 19 | 1.0000 | 0.7088 | 0.8065 | 0.3684 | 0.5789 | 1.0000 | 0.0000 | 2409.47 |
| Gemini-MM | 5 | 1.0000 | 0.8333 | 0.8333 | 0.6000 | 0.6000 | 1.0000 | 0.0000 | 3570.40 |

## 9. 결과 분석

### 9.1 Tool 선택 성능

Gemini와 Gemini-MM은 모두 Tool Accuracy 1.0을 기록했다. 이는 모델이 텍스트 instruction뿐 아니라 이미지와 음성 컨텍스트에서도 어떤 Tool을 호출해야 하는지 정확히 판단했음을 의미한다.

Random baseline의 Tool Accuracy는 0.1579로 낮았다. 이는 Tool 선택 문제가 단순한 우연으로 해결될 수 없으며, 사용자 의도와 컨텍스트 해석이 필요하다는 점을 보여준다.

Keyword baseline은 0.9474로 높게 나타났다. 현재 텍스트 데이터 일부는 키워드가 명확하기 때문에 규칙 기반 방식도 Tool 선택에서는 강하게 동작했다. 하지만 Keyword 방식은 argument 추출 성능이 낮고, 이미지/음성 같은 비정형 컨텍스트를 직접 처리하지 못한다.

### 9.2 Argument 추출 성능

Gemini의 strict Argument F1은 0.7088이고, normalized Argument F1은 0.8065이다. 정규화 후 점수가 상승한 이유는 `"오후 2시"`와 `"14:00"`처럼 의미는 같지만 표현이 다른 시간 값이 보정되었기 때문이다.

Gemini-MM의 Argument F1은 0.8333으로 나타났다. 이미지 샘플에서는 회의 제목, 날짜, 시간, 위치 정보를 정확히 읽어 Tool arguments로 변환했다. 음성 샘플에서도 이메일 수신자, 제목, 본문과 슬랙 채널, 메시지를 추출했다.

다만 음성 샘플에서 `"Assignment submission"`과 `"Assignment Submission"`, `"ten minutes"`와 `"10 minutes"`처럼 의미는 같지만 표기가 다른 경우가 발생했다. 이 때문에 Tool 선택은 정확했지만 Exact Match는 0.6으로 제한되었다.

### 9.3 JSON 안정성과 Tool hallucination

모든 방법에서 JSON Success Rate는 1.0이었다. 특히 Gemini와 Gemini-MM은 LLM 출력임에도 정상적인 JSON 구조를 유지했다.

Hallucinated Tool Rate는 0.0이었다. 즉, 모델이 `tools.json`에 존재하지 않는 Tool 이름을 생성하지 않았다. Agent 시스템에서는 존재하지 않는 Tool 호출이 실행 오류로 이어질 수 있으므로, 이 지표가 0이라는 점은 중요하다.

### 9.4 지연 시간

Gemini의 평균 지연 시간은 약 2.4초, Gemini-MM의 평균 지연 시간은 약 3.57초였다. 멀티모달 입력은 이미지와 음성 파일을 함께 처리하므로 텍스트 전용보다 지연 시간이 증가했다.

MVP 수준에서는 충분히 사용 가능한 속도지만, 실제 서비스에 적용하려면 다음 최적화가 필요하다.

- 자주 쓰는 Tool 목록 prompt 축약
- 이미지/음성 전처리 또는 캐싱
- 경량 모델 사용
- 비동기 처리
- 실패 시 retry/backoff 적용

## 10. 구현 파일

주요 구현 파일은 다음과 같다.

| 파일 | 역할 |
|---|---|
| `tools.json` | 사용 가능한 Tool 정의 |
| `data/test_data.jsonl` | 텍스트 기반 평가 데이터 |
| `data/multimodal_test_data.jsonl` | 이미지/음성 기반 멀티모달 평가 데이터 |
| `data/media/` | 멀티모달 이미지/음성 파일 |
| `scripts/generate_multimodal_assets.ps1` | 발표용 이미지/음성 샘플 생성 |
| `src/predict_gemini.py` | Gemini 기반 텍스트/멀티모달 Tool-Action 예측 |
| `src/baselines.py` | Random, Keyword baseline |
| `src/evaluate.py` | 평가 지표 계산 |
| `src/make_result_table.py` | 결과표 CSV 생성 |
| `outputs/predictions_gemini_multimodal.jsonl` | 멀티모달 예측 결과 |
| `outputs/evaluation_gemini_multimodal.json` | 멀티모달 평가 결과 |
| `outputs/result_table.csv` | 최종 결과표 |

## 11. 실행 방법

멀티모달 샘플 자산 생성:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\generate_multimodal_assets.ps1
```

멀티모달 예측:

```bash
python src/predict_gemini.py --tools tools.json --data data/multimodal_test_data.jsonl --output outputs/predictions_gemini_multimodal.jsonl
```

로컬 인증서 문제로 Gemini 호출이 실패하면 다음과 같이 실행할 수 있다.

```powershell
$env:GEMINI_ALLOW_INSECURE_SSL='1'; python src\predict_gemini.py --tools tools.json --data data\multimodal_test_data.jsonl --output outputs\predictions_gemini_multimodal.jsonl
```

멀티모달 평가:

```bash
python src/evaluate.py --tools tools.json --predictions outputs/predictions_gemini_multimodal.jsonl --output outputs/evaluation_gemini_multimodal.json --detail outputs/evaluation_detail_gemini_multimodal.csv
```

결과표 생성:

```bash
python src/make_result_table.py --inputs outputs/evaluation_random.json outputs/evaluation_keyword.json outputs/evaluation_gemini.json outputs/evaluation_gemini_multimodal.json --names Random Keyword Gemini Gemini-MM --output outputs/result_table.csv
```

## 12. 한계 및 개선 방향

첫째, 멀티모달 샘플 수가 5개로 작다. 이미지와 음성을 실제 입력으로 사용한다는 구조는 검증했지만, 일반화 성능을 주장하려면 더 많은 샘플이 필요하다.

둘째, 현재 정규화는 주로 시간 표현 중심이다. 음성 샘플에서 나타난 대소문자 차이, 숫자 표기 차이, 의미 동등 표현을 더 잘 처리하려면 argument normalization을 확장해야 한다.

셋째, 실제 Tool 실행은 수행하지 않았다. 본 프로젝트는 실행 직전의 행동 의사결정 예측을 평가하는 데 집중했다. 실제 서비스로 확장하려면 Tool 호출 전 validation layer, 사용자 확인 단계, 권한 제어, 위험 행동 감지 등이 필요하다.

넷째, 이미지와 음성 샘플은 발표용으로 생성한 통제된 데이터다. 실제 환경에서는 화면 캡처, 모바일 UI, 회의 녹음, 노이즈가 있는 음성 등 더 복잡한 입력이 들어올 수 있다.

개선 방향은 다음과 같다.

- 멀티모달 샘플 수 확대
- 실제 UI 스크린샷 기반 데이터 추가
- 음성 노이즈와 다양한 화자 데이터 추가
- 날짜, 숫자, 고유명사, 대소문자 정규화 강화
- LLM-as-judge 기반 의미 평가 추가
- Tool 실행 전 안전성 검증 모듈 추가

## 13. 예상 질문과 답변

### Q1. 실제 이메일이나 캘린더를 실행하지 않은 이유는 무엇인가?

본 프로젝트의 목표는 실제 실행이 아니라 Agent의 다음 행동 의사결정을 예측하고 평가하는 것이다. 실제 실행은 외부 서비스 인증, 권한, 안전 문제가 있으므로 MVP에서는 JSON 행동 계획까지만 생성했다.

### Q2. 멀티모달이라고 볼 수 있는 근거는 무엇인가?

`predict_gemini.py`가 `image_path`와 `audio_path`에 있는 실제 이미지/음성 파일을 읽어 Gemini API의 멀티모달 입력으로 전달한다. 즉, OCR이나 전사 결과를 미리 텍스트로 넣은 것이 아니라 이미지와 음성 자체를 모델 입력에 포함했다.

### Q3. Keyword baseline도 높은데 LLM이 필요한가?

현재 텍스트 데이터 일부는 키워드가 명확해서 Keyword baseline도 높게 나왔다. 그러나 Keyword 방식은 이미지와 음성을 직접 처리할 수 없고, 복합 명령, 부정 표현, 유사 Tool 구분, 다양한 표현에 취약하다. LLM은 Tool 설명과 멀티모달 컨텍스트를 함께 해석할 수 있다는 장점이 있다.

### Q4. Exact Match가 낮은데 성능이 좋은 것인가?

Exact Match는 문자열까지 완전히 같아야 하므로 매우 엄격하다. 예를 들어 `"ten minutes"`와 `"10 minutes"`는 의미가 같지만 strict 기준에서는 다르게 처리된다. 따라서 Tool Accuracy, Argument F1, normalized 지표를 함께 봐야 한다.

### Q5. 실제 서비스 적용이 가능한가?

현재 평균 지연 시간은 텍스트 Gemini 약 2.4초, 멀티모달 Gemini 약 3.57초다. MVP 수준에서는 사용 가능하지만, 실제 서비스에서는 prompt 최적화, 캐싱, 비동기 처리, 안전성 검증이 필요하다.

## 14. 결론

본 프로젝트는 사용자 instruction과 Tool 목록을 기반으로 LLM Agent의 다음 Tool-Action JSON을 예측하고, 이를 정답과 비교하여 정량적으로 평가하는 파이프라인을 구현했다. 또한 이미지와 음성 컨텍스트를 실제 모델 입력에 포함하도록 확장하여 멀티모달 기반 Agent 행동 의사결정 예측 구조를 완성했다.

실험 결과 Gemini는 텍스트 기반 평가에서 Tool Accuracy 1.0, normalized Argument F1 0.8065를 기록했다. 멀티모달 평가인 Gemini-MM은 이미지 3개와 음성 2개 샘플에서 Tool Accuracy 1.0, Argument F1 0.8333, JSON Success Rate 1.0을 기록했다.

따라서 본 프로젝트는 텍스트, 이미지, 음성 컨텍스트를 활용하여 LLM Agent가 다음에 수행해야 할 행동을 예측하고 평가할 수 있음을 보였다. 이는 멀티모달 Agent 시스템에서 실제 Tool 실행 전 의사결정 단계를 검증하는 기초 파이프라인으로 활용될 수 있다.
