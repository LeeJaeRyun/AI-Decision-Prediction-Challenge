너는 Python 개발자다. 아래 요구사항에 맞춰 “LLM Agent Tool-Action 예측 평가 MVP” 프로젝트를 구현해줘.

목표:
사용자 자연어 지시문과 사용 가능한 Tool 목록을 입력으로 받아, OpenAI ChatGPT API가 다음에 호출해야 할 Tool-Action JSON을 예측하게 한다. 이후 정답 gold_action과 예측 pred_action을 비교해서 Tool Accuracy, Argument F1, Exact Match, JSON Success Rate를 계산한다.

중요:
- LLM 자체를 새로 학습하지 않는다.
- 실제 이메일/캘린더/슬랙을 실행하지 않는다.
- 모델은 “실행할 행동 JSON”만 예측한다.
- 결과 숫자는 절대 임의로 만들지 말고 evaluate.py가 실제 predictions.jsonl을 읽어서 계산하게 한다.
- 코드가 바로 실행 가능해야 한다.
- 한국어 사용자 지시문 샘플을 사용한다.

프로젝트 구조는 다음처럼 만들어줘.

tool_action_mvp/
  README.md
  requirements.txt
  .env.example
  tools.json
  data/
    test_data.jsonl
  src/
    predict_openai.py
    evaluate.py
    baselines.py
    make_result_table.py
  outputs/
    .gitkeep

1. tools.json 요구사항:
Tool은 최소 10개 이상 정의한다.
각 Tool은 다음 필드를 가진다.

{
  "tool_name": "calendar.create_event",
  "description": "새로운 캘린더 일정을 생성한다.",
  "parameters": ["title", "date", "time"]
}

포함할 Tool 예시:
- calendar.create_event
- calendar.update_event
- weather.search
- email.send
- slack.send_message
- reminder.create
- web.search
- file.create_document
- todo.create_task
- map.search_place
- translate.text
- calculator.calculate

2. data/test_data.jsonl 요구사항:
한국어 테스트 샘플을 최소 50개 만들어줘.
각 줄은 JSON 객체 하나여야 한다.
각 샘플은 다음 형식을 따른다.

{
  "id": 1,
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

주의:
- gold_action.tool_name은 반드시 tools.json에 있는 tool_name 중 하나여야 한다.
- arguments key는 해당 Tool의 parameters와 최대한 맞춰라.
- 쉬운 샘플, 애매한 샘플, 유사 Tool이 헷갈리는 샘플을 섞어라.
- 예: “내일 서울 비 와?”는 weather.search
- 예: “교수님께 과제 제출 메일 보내줘”는 email.send
- 예: “팀 채널에 회의 취소됐다고 알려줘”는 slack.send_message
- 예: “오늘 할 일에 자료조사 추가해줘”는 todo.create_task

3. src/predict_openai.py 요구사항:
OpenAI Python SDK를 사용한다.
환경변수 OPENAI_API_KEY에서 API 키를 읽는다.
환경변수 OPENAI_MODEL이 있으면 그 모델을 쓰고, 없으면 기본 모델을 코드 상단 상수로 지정한다.
입력:
- --tools tools.json
- --data data/test_data.jsonl
- --output outputs/predictions_openai.jsonl
- --limit 선택 옵션

동작:
- tools.json과 test_data.jsonl을 읽는다.
- 각 instruction에 대해 OpenAI API를 호출한다.
- 프롬프트에는 사용자 지시문과 사용 가능한 Tool 목록을 넣는다.
- 모델은 반드시 아래 형식으로만 응답해야 한다.

{
  "tool_name": "string",
  "arguments": {
    "key": "value"
  }
}

- 가능하면 OpenAI Structured Outputs 또는 Pydantic schema를 사용해서 JSON 파싱 안정성을 높여라.
- API 호출 실패 시 프로그램이 전체 중단되지 않게 error 필드를 기록하고 다음 샘플로 넘어가라.
- 출력 predictions_openai.jsonl의 각 줄은 아래 형식이어야 한다.

{
  "id": 1,
  "instruction": "...",
  "gold_action": {...},
  "pred_action": {...},
  "json_success": true,
  "error": null,
  "latency_ms": 1234
}

- pred_action 파싱 실패 시:
  - pred_action은 null
  - json_success는 false
  - error에 이유 저장

4. src/evaluate.py 요구사항:
입력:
- --predictions outputs/predictions_openai.jsonl
- --output outputs/evaluation_openai.json
- --detail outputs/evaluation_detail_openai.csv

계산할 지표:
1) Tool Accuracy
- pred_action.tool_name == gold_action.tool_name 인 비율

2) Argument F1
- gold_action.arguments와 pred_action.arguments를 key-value 쌍 단위로 비교한다.
- 예: {"date": "내일", "time": "14:00"}는 ("date", "내일"), ("time", "14:00")로 비교
- 각 샘플별 precision, recall, f1을 계산하고 전체 평균을 낸다.
- pred_action이 null이면 f1 = 0

3) Exact Match
- tool_name과 arguments가 완전히 같으면 1, 아니면 0

4) JSON Success Rate
- json_success == true 인 비율

5) Hallucinated Tool Rate
- pred_action.tool_name이 tools.json에 없는 경우의 비율
- evaluate.py에서 --tools 옵션도 받을 수 있게 해서 tool 존재 여부를 확인하라.

상세 CSV에는 다음 컬럼을 넣어라.
- id
- instruction
- gold_tool
- pred_tool
- tool_correct
- argument_f1
- exact_match
- json_success
- hallucinated_tool
- gold_action
- pred_action
- error

5. src/baselines.py 요구사항:
OpenAI API 없이 비교용 baseline 예측도 구현한다.

입력:
- --tools tools.json
- --data data/test_data.jsonl
- --method random 또는 keyword
- --output outputs/predictions_random.jsonl 또는 outputs/predictions_keyword.jsonl

random baseline:
- tools.json에서 무작위 tool 하나를 고른다.
- arguments는 빈 dict로 둔다.
- seed는 42로 고정한다.

keyword baseline:
- instruction에 포함된 한국어 키워드로 tool을 고른다.
- 예:
  - “일정”, “회의”, “캘린더” → calendar.create_event
  - “날씨”, “비”, “기온” → weather.search
  - “메일”, “이메일”, “교수님” → email.send
  - “슬랙”, “채널”, “팀에 알려” → slack.send_message
  - “알림”, “리마인더” → reminder.create
  - “검색”, “찾아” → web.search
  - “문서”, “파일” → file.create_document
  - “할 일”, “todo”, “작업” → todo.create_task
  - “장소”, “지도”, “근처” → map.search_place
  - “번역” → translate.text
  - “계산” → calculator.calculate
- arguments는 빈 dict 또는 instruction에서 간단히 추출 가능한 값만 넣어라.
- 출력 포맷은 OpenAI predictions와 동일하게 맞춘다.

6. src/make_result_table.py 요구사항:
여러 evaluation JSON 파일을 읽어서 결과표 CSV를 만든다.
입력 예:
- --inputs outputs/evaluation_random.json outputs/evaluation_keyword.json outputs/evaluation_openai.json
- --names Random Keyword OpenAI
- --output outputs/result_table.csv

출력 CSV 컬럼:
- method
- total
- tool_accuracy
- argument_f1
- exact_match
- json_success_rate
- hallucinated_tool_rate
- avg_latency_ms

7. README.md 요구사항:
초보자가 따라할 수 있게 작성한다.
포함 내용:
- 프로젝트 설명
- 설치 방법
- .env 설정 방법
- 실행 순서
- random baseline 실행
- keyword baseline 실행
- OpenAI 예측 실행
- 평가 실행
- 결과표 생성
- 결과보고서에 쓸 수 있는 문장 예시

실행 예시는 아래처럼 작성한다.

python src/baselines.py --tools tools.json --data data/test_data.jsonl --method random --output outputs/predictions_random.jsonl
python src/evaluate.py --tools tools.json --predictions outputs/predictions_random.jsonl --output outputs/evaluation_random.json --detail outputs/evaluation_detail_random.csv

python src/baselines.py --tools tools.json --data data/test_data.jsonl --method keyword --output outputs/predictions_keyword.jsonl
python src/evaluate.py --tools tools.json --predictions outputs/predictions_keyword.jsonl --output outputs/evaluation_keyword.json --detail outputs/evaluation_detail_keyword.csv

python src/predict_openai.py --tools tools.json --data data/test_data.jsonl --output outputs/predictions_openai.jsonl --limit 50
python src/evaluate.py --tools tools.json --predictions outputs/predictions_openai.jsonl --output outputs/evaluation_openai.json --detail outputs/evaluation_detail_openai.csv

python src/make_result_table.py --inputs outputs/evaluation_random.json outputs/evaluation_keyword.json outputs/evaluation_openai.json --names Random Keyword OpenAI --output outputs/result_table.csv

8. requirements.txt:
필요한 패키지를 적어라.
예:
openai
pydantic
python-dotenv
pandas

9. 코드 품질:
- Python 3.10 이상 기준
- 함수 분리
- 타입 힌트 사용
- 파일 없을 때 친절한 에러 메시지
- JSONL 읽기/쓰기 유틸 함수 작성
- ensure_ascii=False 사용해서 한국어 깨지지 않게 저장
- 실행 중 진행 상황 print
- API 비용 절약을 위해 --limit 옵션 제공

10. 최종적으로 구현 후:
- 각 파일의 내용을 생성해라.
- 실행 방법을 README에 적어라.
- 가능한 경우 간단한 dry-run 또는 random/keyword baseline은 실제로 실행해서 outputs 예시가 생기게 해라.
- OpenAI API 키가 없으면 predict_openai.py는 실행하지 않아도 되지만, 코드 자체는 완성해라.

이 프로젝트의 목적은 결과보고서에 다음과 같은 결과표를 만들기 위한 것이다.

method, Tool Accuracy, Argument F1, Exact Match, JSON Success Rate
Random, ...
Keyword, ...
OpenAI, ...

절대 임의 숫자를 쓰지 말고, evaluate.py가 산출한 값만 사용하게 구현해라.