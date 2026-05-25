# LLM Agent Tool-Action 예측 평가 MVP 결과 보고서

## 1. 프로젝트 개요

본 프로젝트는 **AI Agent 행동(Action) 의사결정 예측 챌린지**를 주제로 한다. 사용자의 자연어 지시문과 사용 가능한 Tool 목록이 주어졌을 때, Agent가 다음 단계에서 호출해야 할 Tool과 arguments를 JSON 형태로 예측하는 문제를 다룬다.

예를 들어 사용자가 "내일 오후 2시에 팀 회의 일정 잡아줘."라고 지시하면, Agent는 실제 캘린더를 실행하는 것이 아니라 다음과 같은 행동 계획 JSON을 출력해야 한다.

```json
{
  "tool_name": "calendar.create_event",
  "arguments": {
    "title": "팀 회의",
    "date": "내일",
    "time": "14:00"
  }
}
```

본 프로젝트의 핵심은 **LLM이 직접 업무를 실행하지 않고, 실행해야 할 행동을 구조화된 JSON으로 예측하게 하는 것**이다. 따라서 이메일 전송, 캘린더 등록, 슬랙 메시지 전송 등 실제 외부 서비스 호출은 수행하지 않는다. 대신 예측 결과와 정답을 비교하여 Tool 선택 정확도와 인자 추출 성능을 평가한다.

## 2. 주제 적합성

본 프로젝트는 AI Agent가 실제 환경에서 수행하는 의사결정 단계 중 **"어떤 Tool을 호출할 것인가"**와 **"어떤 인자를 넣을 것인가"**를 예측 대상으로 삼았다. 이는 AI Agent 행동 의사결정 예측이라는 챌린지 주제와 직접적으로 연결된다.

일반적인 챗봇은 자연어 답변을 생성하는 데 초점을 두지만, Agent 시스템은 사용자의 목적을 달성하기 위해 외부 Tool을 선택하고 호출해야 한다. 이때 잘못된 Tool을 선택하거나 잘못된 arguments를 생성하면 실제 서비스에서는 잘못된 메일 발송, 잘못된 일정 등록, 잘못된 검색 수행으로 이어질 수 있다.

따라서 본 프로젝트는 다음 세 가지 측면에서 주제에 적합하다.

- 사용자 지시문을 Agent의 다음 행동 JSON으로 변환한다.
- Tool 목록이 명시적으로 주어진 상황에서 Tool 선택 문제를 평가한다.
- 정답 `gold_action`과 예측 `pred_action`을 비교하여 행동 의사결정 품질을 수치화한다.

## 3. 문제 정의

### 3.1 입력과 출력

문제는 다음과 같이 정의했다.

입력:

- 한국어 사용자 지시문
- 사용 가능한 Tool 목록
- 각 Tool의 설명과 parameters

출력:

- 다음에 호출해야 할 Tool-Action JSON

출력 형식:

```json
{
  "tool_name": "string",
  "arguments": {
    "key": "value"
  }
}
```

정답 데이터는 `gold_action`, 모델 예측은 `pred_action`으로 저장했다. 평가 스크립트는 예측 파일인 `predictions.jsonl`을 읽어서 실제 지표를 계산한다. 즉, 결과표의 숫자는 사람이 임의로 작성한 값이 아니라 평가 코드가 산출한 값이다.

### 3.2 해결해야 할 핵심 문제

이 과제에서 해결해야 할 문제는 단순 분류보다 복합적이다.

첫째, 사용자의 의도를 파악하여 Tool을 선택해야 한다. 예를 들어 "내일 서울 비 와?"는 `weather.search`이고, "교수님께 과제 제출 메일 보내줘"는 `email.send`이다.

둘째, Tool 선택 후 arguments를 추출해야 한다. "내일 오후 2시에 팀 회의 일정 잡아줘"라는 지시문에서는 `title`, `date`, `time`을 추출해야 한다.

셋째, 유사한 Tool 간 혼동을 줄여야 한다. 예를 들어 "회의 자료 찾아서 문서로 만들어줘"는 검색 의도가 강하고, "회의 자료 문서 만들어줘"는 문서 생성 의도가 강하다. 또한 "내일 발표 준비를 할 일에 넣어줘. 일정 등록은 하지 마."는 캘린더가 아니라 todo Tool을 선택해야 한다.

## 4. 데이터 구성 및 분석

### 4.1 Tool 목록

`tools.json`에는 총 12개의 Tool을 정의했다.

| Tool | 목적 |
|---|---|z
| `calendar.create_event` | 새 캘린더 일정 생성 |
| `calendar.update_event` | 기존 일정 수정 |
| `weather.search` | 날씨 조회 |
| `email.send` | 이메일 전송 행동 생성 |
| `slack.send_message` | 슬랙 메시지 전송 행동 생성 |
| `reminder.create` | 알림 생성 |
| `web.search` | 웹 검색 |
| `file.create_document` | 문서 생성 |
| `todo.create_task` | 할 일 추가 |
| `map.search_place` | 장소 검색 |
| `translate.text` | 번역 |
| `calculator.calculate` | 계산 |

각 Tool은 `tool_name`, `description`, `parameters` 필드를 가진다. 이 구조를 통해 LLM이 단순히 이름만 보고 Tool을 고르는 것이 아니라, Tool 설명과 인자 목록을 함께 참고할 수 있도록 했다.

### 4.2 테스트 데이터

최종 실험 데이터는 Gemini API 응답이 정상적으로 저장된 19개 샘플을 기준으로 구성했다. 모든 샘플은 한국어 사용자 지시문이며, 각 샘플에는 정답 `gold_action`이 포함되어 있다.

데이터 분포는 다음과 같다.

| Tool | 샘플 수 |
|---|---:|
| `calendar.create_event` | 5 |
| `calendar.update_event` | 3 |
| `weather.search` | 4 |
| `email.send` | 4 |
| `web.search` | 1 |
| `todo.create_task` | 2 |
| 합계 | 19 |

### 4.3 데이터 분석 방향

데이터는 쉬운 지시문과 헷갈릴 수 있는 지시문을 함께 포함하도록 구성했다.

쉬운 예시는 명확한 키워드가 포함된 문장이다.

- "내일 서울 비 와?" -> `weather.search`
- "교수님께 과제 제출 메일 보내줘." -> `email.send`

혼동 가능성이 있는 예시는 유사 Tool 간 구분이 필요한 문장이다.

- 일정 생성과 일정 수정 구분
- todo와 calendar 구분
- web.search와 file.create_document 구분

이러한 데이터 구성은 Agent가 단순 키워드 매칭만으로 행동을 고르는 것이 아니라, 문장의 실제 의도와 Tool 역할을 함께 판단해야 함을 보여준다.

## 5. 해결 아이디어

### 5.1 전체 접근 방식

본 프로젝트는 LLM을 새로 학습하지 않고, 기존 LLM API를 사용해 Tool-Action JSON을 예측한다. 구현은 다음 흐름으로 구성했다.

1. `tools.json`에서 사용 가능한 Tool 목록을 읽는다.
2. `data/test_data.jsonl`에서 사용자 지시문과 정답을 읽는다.
3. baseline 또는 LLM이 `pred_action`을 생성한다.
4. `evaluate.py`가 `gold_action`과 `pred_action`을 비교한다.
5. 평가 결과를 JSON, CSV, 결과표 CSV로 저장한다.

### 5.2 비교 모델

성능 비교를 위해 세 가지 방법을 사용했다.

| 방법 | 설명 |
|---|---|
| Random | 무작위로 Tool을 선택하고 arguments는 빈 dict로 둔다. |
| Keyword | 한국어 키워드 규칙으로 Tool을 선택한다. |
| Gemini | Gemini API를 호출해 Tool-Action JSON을 생성한다. |

Random baseline은 최소 기준선 역할을 한다. Keyword baseline은 간단한 규칙 기반 시스템이 어느 정도까지 동작하는지 확인하는 비교 기준이다. Gemini는 LLM 기반 방법으로, 문맥 이해와 argument 추출 능력을 확인하기 위해 사용했다.

### 5.3 참신성 및 적합성

단순히 LLM 답변을 생성하는 것이 아니라, Agent 실행 직전 단계인 **Tool-Action JSON 예측**을 평가 대상으로 삼은 점이 핵심이다. 또한 Tool Accuracy뿐 아니라 Argument F1, Exact Match, JSON Success Rate, Hallucinated Tool Rate를 함께 사용하여 Agent 행동의 품질을 여러 관점에서 평가했다.

추가로 `"14:00"`과 `"오후 2시"`처럼 의미는 같지만 문자열이 다른 경우를 보완하기 위해 `normalized_argument_f1`, `normalized_exact_match`를 추가했다. 이 보조 지표는 strict string match의 한계를 줄이고, 실제 서비스 관점에서 의미적으로 맞는 예측을 더 잘 반영한다.

## 6. 모델 설계 및 구현

### 6.1 프로젝트 구조

```text
tool_action_mvp/
  README.md
  REPORT.md
  requirements.txt
  .env.example
  tools.json
  data/
    test_data.jsonl
  src/
    utils.py
    baselines.py
    predict_openai.py
    predict_gemini.py
    evaluate.py
    make_result_table.py
  outputs/
    result_table.csv
```

### 6.2 주요 구현 파일

| 파일 | 역할 |
|---|---|
| `src/utils.py` | JSON/JSONL 읽기, 쓰기, Tool 이름 로딩 유틸 |
| `src/baselines.py` | Random 및 Keyword baseline 예측 생성 |
| `src/predict_openai.py` | OpenAI API 기반 예측 코드 |
| `src/predict_gemini.py` | Gemini API 기반 예측 코드 |
| `src/evaluate.py` | 평가 지표 계산 및 상세 CSV 생성 |
| `src/make_result_table.py` | 여러 evaluation JSON을 결과표 CSV로 병합 |

### 6.3 Gemini 예측 방식

Gemini 예측 코드는 사용자의 instruction과 전체 Tool 목록을 prompt에 포함한다. 모델에는 다음 조건을 준다.

- 실제 Tool을 실행하지 않는다.
- 사용 가능한 Tool 중 하나를 선택한다.
- JSON 객체 하나만 반환한다.
- 반환 형식은 `tool_name`과 `arguments`를 포함한다.

예측 결과는 다음 형식으로 JSONL에 저장된다.

```json
{
  "id": 1,
  "instruction": "...",
  "gold_action": {...},
  "pred_action": {...},
  "json_success": true,
  "error": null,
  "latency_ms": 1869
}
```

API 호출 실패나 JSON 파싱 실패가 발생하면 프로그램이 중단되지 않고 `error` 필드에 실패 원인을 저장하도록 설계했다.

## 7. 평가 지표

본 프로젝트에서는 다음 지표를 사용했다.

### 7.1 Tool Accuracy

예측한 Tool 이름이 정답 Tool 이름과 같은 비율이다.

```text
pred_action.tool_name == gold_action.tool_name
```

이 지표는 Agent가 어떤 Tool을 호출할지 올바르게 결정했는지를 평가한다.

### 7.2 Argument F1

arguments를 key-value 쌍 단위로 비교한다.

예를 들어 다음 arguments는 두 개의 쌍으로 평가된다.

```json
{
  "date": "내일",
  "time": "14:00"
}
```

비교 단위:

```text
("date", "내일")
("time", "14:00")
```

각 샘플마다 precision, recall, F1을 계산하고 전체 평균을 낸다.

### 7.3 Exact Match

Tool 이름과 arguments가 모두 완전히 같으면 1, 아니면 0으로 계산한다. 가장 엄격한 지표다.

### 7.4 JSON Success Rate

모델 예측이 정상적인 JSON으로 생성 또는 파싱되었는지 평가한다.

### 7.5 Hallucinated Tool Rate

모델이 `tools.json`에 없는 Tool 이름을 만들어낸 비율이다. Agent 시스템에서는 존재하지 않는 Tool을 호출하려는 hallucination이 치명적이므로 별도 지표로 확인했다.

### 7.6 정규화 지표

기본 지표는 문자열 완전일치 기준이므로 `"14:00"`과 `"오후 2시"`를 다르게 판단한다. 하지만 실제 의미는 같다. 이를 보완하기 위해 시간 표현을 정규화한 보조 지표를 추가했다.

| 지표 | 설명 |
|---|---|
| `normalized_argument_f1` | 시간 표현을 정규화한 뒤 계산한 Argument F1 |
| `normalized_exact_match` | 정규화된 arguments 기준 Exact Match |

예:

```text
"오후 2시" -> "14:00"
"오전 10시" -> "10:00"
"3시" -> "03:00" 또는 "15:00" 후보로 비교
```

## 8. 실험 결과

평가 결과는 `outputs/result_table.csv`에 저장된 값을 기준으로 작성했다.

| Method | Total | Tool Accuracy | Argument F1 | Normalized Argument F1 | Exact Match | Normalized Exact Match | JSON Success Rate | Hallucinated Tool Rate | Avg Latency ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Random | 19 | 0.1579 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 0.0000 | 0.00 |
| Keyword | 19 | 0.9474 | 0.4140 | 0.4140 | 0.1579 | 0.1579 | 1.0000 | 0.0000 | 0.00 |
| Gemini | 19 | 1.0000 | 0.7088 | 0.8065 | 0.3684 | 0.5789 | 1.0000 | 0.0000 | 2409.47 |

### 8.1 Tool Accuracy 분석

Gemini는 19개 샘플에서 Tool Accuracy 1.0을 기록했다. 이는 모든 샘플에서 정답 Tool을 선택했다는 의미다. Keyword baseline도 0.9474로 높은 편이지만, 규칙 기반 방식은 데이터가 넓어질수록 키워드 누락과 문맥 오해 문제가 발생할 수 있다.

Random baseline은 0.1579로 낮았다. 이는 Tool 선택 문제가 단순 운에 맡길 수 있는 문제가 아니며, 사용자 의도 분석이 필요함을 보여준다.

### 8.2 Argument F1 분석

Gemini의 strict Argument F1은 0.7088이고, normalized Argument F1은 0.8065이다. 정규화 후 점수가 상승한 이유는 Gemini가 `"오후 2시"`, `"오전 9시"`처럼 사람이 이해하기 쉬운 자연어 시간 표현을 반환하는 경우가 있었기 때문이다.

예를 들어 정답이 `"14:00"`이고 예측이 `"오후 2시"`인 경우, strict 평가에서는 불일치지만 정규화 평가에서는 의미적으로 일치한다. 따라서 normalized Argument F1은 실제 사용 관점에서 더 합리적인 보조 지표다.

### 8.3 Exact Match 분석

Gemini의 strict Exact Match는 0.3684이고 normalized Exact Match는 0.5789이다. Exact Match는 매우 엄격한 지표이므로 title, date, time 중 하나라도 표현이 다르면 실패로 계산된다. 하지만 normalized 기준에서는 시간 표현 차이를 보정하기 때문에 점수가 개선된다.

### 8.4 JSON Success Rate 및 Hallucinated Tool Rate

Gemini의 JSON Success Rate는 1.0이다. 이는 최종 실험 데이터 19개에 대해 모두 정상적인 JSON 예측이 저장되었음을 의미한다. Hallucinated Tool Rate도 0.0으로, 존재하지 않는 Tool을 생성한 사례가 없었다.

Agent 시스템에서 JSON 구조 안정성과 Tool hallucination 방지는 중요하다. JSON이 깨지면 후속 실행기가 동작할 수 없고, 존재하지 않는 Tool을 호출하면 실행 단계에서 오류가 발생한다. 본 구현은 이러한 실패를 별도 지표로 추적할 수 있도록 설계했다.

## 9. 추론 속도 및 효율성

Gemini의 평균 지연 시간은 2409.47ms로 측정되었다. 즉, 한 입력에 대해 약 2.4초 내외로 Tool-Action JSON을 생성했다.

실시간 서비스 관점에서 2~3초 응답은 간단한 개인 비서형 Agent나 업무 자동화 프로토타입에는 적용 가능한 수준이다. 다만 대규모 트래픽 서비스에서는 다음 최적화가 필요하다.

- Tool 목록 prompt 압축
- 자주 쓰는 Tool 선택 결과 캐싱
- 경량 모델 사용
- batch 처리 또는 비동기 큐 사용
- 실패 시 retry/backoff 적용

Random과 Keyword baseline은 API 호출이 없기 때문에 지연 시간이 사실상 0ms에 가깝다. 그러나 두 방식은 문맥 이해나 argument 추출 능력이 제한적이다. 따라서 실제 Agent 서비스에서는 속도와 정확도의 균형을 고려해, 간단한 명령은 rule-based 방식으로 처리하고 복잡한 명령은 LLM으로 넘기는 hybrid 구조도 가능하다.

## 10. 코드 완성도 및 실행 가능성

본 프로젝트는 명령어 기반으로 바로 실행 가능하도록 구성했다.

Random baseline:

```bash
python src/baselines.py --tools tools.json --data data/test_data.jsonl --method random --output outputs/predictions_random.jsonl
python src/evaluate.py --tools tools.json --predictions outputs/predictions_random.jsonl --output outputs/evaluation_random.json --detail outputs/evaluation_detail_random.csv
```

Keyword baseline:

```bash
python src/baselines.py --tools tools.json --data data/test_data.jsonl --method keyword --output outputs/predictions_keyword.jsonl
python src/evaluate.py --tools tools.json --predictions outputs/predictions_keyword.jsonl --output outputs/evaluation_keyword.json --detail outputs/evaluation_detail_keyword.csv
```

Gemini:

```bash
python src/predict_gemini.py --tools tools.json --data data/test_data.jsonl --output outputs/predictions_gemini.jsonl --limit 19
python src/evaluate.py --tools tools.json --predictions outputs/predictions_gemini.jsonl --output outputs/evaluation_gemini.json --detail outputs/evaluation_detail_gemini.csv
```

결과표 생성:

```bash
python src/make_result_table.py --inputs outputs/evaluation_random.json outputs/evaluation_keyword.json outputs/evaluation_gemini.json --names Random Keyword Gemini --output outputs/result_table.csv
```

코드 품질 측면에서는 다음을 반영했다.

- Python 3.10 이상 기준
- 함수 분리
- 타입 힌트 사용
- JSONL 읽기/쓰기 유틸 함수 작성
- `ensure_ascii=False`로 한국어 저장
- 파일이 없을 때 명확한 오류 메시지 제공
- API 실패 시 전체 프로그램 중단 방지
- `.env`와 `.gitignore`로 API 키 노출 방지

## 11. 결과 해석

실험 결과 Gemini는 모든 샘플에서 올바른 Tool을 선택했다. 이는 LLM이 단순 키워드가 아니라 문장의 의도와 Tool 설명을 함께 활용해 행동을 결정할 수 있음을 보여준다.

반면 arguments에서는 strict 기준과 normalized 기준 사이에 차이가 있었다. 이는 모델이 의미적으로는 맞는 값을 생성했지만, 정답 데이터의 표기 방식과 다르게 표현했기 때문이다. 특히 시간 표현에서 `"14:00"`과 `"오후 2시"` 같은 차이가 많이 발생했다.

따라서 본 프로젝트는 다음 결론을 제시한다.

1. LLM 기반 Agent는 Tool 선택 문제에서 강한 성능을 보였다.
2. arguments 추출은 의미적으로 적절하지만 표준 포맷 정규화가 필요하다.
3. strict Exact Match만으로는 실제 Agent 행동 품질을 과소평가할 수 있다.
4. Tool Accuracy, Argument F1, JSON Success Rate, Hallucinated Tool Rate를 함께 봐야 한다.

## 12. 한계 및 개선 방향

### 12.1 데이터 규모

최종 실험은 19개 샘플을 기준으로 진행했다. MVP 단계에서는 구조 검증에 충분하지만, 더 일반적인 성능을 주장하려면 더 많은 한국어 지시문과 다양한 Tool 조합이 필요하다.

개선 방향:

- Tool별 균형 잡힌 샘플 수 확보
- 더 많은 애매한 지시문 추가
- 복합 명령 데이터 추가
- 날짜, 장소, 사람 이름 등 entity 다양화

### 12.2 정규화 범위

현재 정규화는 주로 시간 표현에 초점을 맞춘다. 하지만 실제 서비스에서는 날짜, 장소, 수신자, 제목 표현도 정규화가 필요하다.

개선 방향:

- 날짜 정규화: "내일", "다음 주 월요일" 처리
- 시간 정규화: 오전/오후, 저녁, 밤 표현 확장
- 텍스트 유사도 기반 argument 평가
- LLM-as-judge 방식의 의미 평가 추가

### 12.3 실제 실행 검증 부재

본 프로젝트는 의도적으로 실제 이메일, 캘린더, 슬랙 실행을 하지 않았다. 이는 안전한 MVP 설계에는 적합하지만, 실제 서비스에서는 Tool 실행 전 validation layer가 추가로 필요하다.

개선 방향:

- Tool schema validation 강화
- 실행 전 사용자 확인 단계 추가
- 위험 행동 감지
- 권한 기반 Tool 호출 제어

## 13. 발표 전달 전략

발표에서는 다음 흐름으로 설명하는 것이 효과적이다.

1. Agent는 답변만 하는 모델이 아니라 Tool을 선택하고 실행하는 시스템임을 설명한다.
2. 본 프로젝트는 실행 직전 단계인 Tool-Action JSON 예측을 평가한다고 설명한다.
3. 데이터 예시를 보여주며 `instruction`, `gold_action`, `pred_action` 구조를 설명한다.
4. Random, Keyword, Gemini를 비교한 이유를 설명한다.
5. 결과표에서 Gemini의 Tool Accuracy 1.0을 강조한다.
6. strict 지표와 normalized 지표 차이를 보여주며 평가의 한계를 설명한다.
7. 실시간 적용 가능성과 개선 방향을 제시한다.

예상 질문과 답변 예시는 다음과 같다.

Q. 왜 실제 Tool을 실행하지 않았는가?

A. 본 과제의 목표는 Agent의 다음 행동 의사결정을 예측하고 평가하는 것이다. 실제 실행은 안전 문제와 외부 서비스 의존성이 있으므로 MVP에서는 JSON 행동 계획까지만 생성했다.

Q. Exact Match가 낮은데 성능이 좋은 것인가?

A. Exact Match는 문자열까지 완전히 같아야 하므로 매우 엄격하다. 예를 들어 `"14:00"`과 `"오후 2시"`는 의미가 같지만 strict 기준에서는 다르게 처리된다. 그래서 시간 표현을 정규화한 normalized 지표를 함께 제시했다.

Q. Keyword baseline도 높은데 LLM이 꼭 필요한가?

A. 현재 데이터 일부는 키워드가 명확해서 Keyword baseline도 높게 나온다. 하지만 복합 명령, 부정 표현, 유사 Tool 구분, 다양한 문장 표현이 늘어나면 규칙 기반 방식은 확장성이 떨어진다. LLM은 Tool 설명과 문맥을 함께 활용할 수 있다는 장점이 있다.

Q. 실시간 서비스에 적용 가능한가?

A. Gemini 평균 지연 시간은 약 2.4초로 MVP 수준에서는 적용 가능하다. 다만 대규모 서비스에서는 prompt 최적화, 캐싱, 경량 모델, 비동기 처리 등이 필요하다.

## 14. 결론

본 프로젝트는 한국어 사용자 지시문을 기반으로 AI Agent의 다음 Tool-Action JSON을 예측하고, 이를 정답과 비교해 정량적으로 평가하는 MVP를 구현했다. Random, Keyword, Gemini를 비교한 결과 Gemini는 19개 샘플에서 Tool Accuracy 1.0을 기록했으며, normalized Argument F1도 0.8065로 가장 높은 성능을 보였다.

이를 통해 LLM 기반 방식이 Agent 행동 의사결정 예측에 효과적임을 확인했다. 또한 strict 문자열 평가만으로는 의미적으로 올바른 예측을 과소평가할 수 있으므로, 시간 표현 정규화와 같은 보조 평가가 필요하다는 점도 확인했다.

최종적으로 본 프로젝트는 챌린지 주제에 맞춰 문제 정의, 데이터 구성, 모델 구현, 성능 평가, 추론 속도 분석까지 포함한 실행 가능한 Agent Tool-Action 예측 평가 파이프라인을 제시한다.
