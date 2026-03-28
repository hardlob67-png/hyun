import os
import io
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from anthropic import Anthropic
from dotenv import load_dotenv
import openpyxl

load_dotenv()

app = Flask(__name__)
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

NO_MARKDOWN = "\n\n[중요] 출력 시 마크다운 문법(**, *, ##, ###, ``` 등)을 절대 사용하지 마세요. 순수 텍스트로만 작성하세요. 강조가 필요하면 대괄호[ ]나 화살표→를 사용하세요."

PROMPTS = {
    "translate": """당신은 영어 교육 전문가입니다. 아래 작업을 수행하세요:

규칙
- 사용자가 영어와 한글 번역을 함께 제공한 경우: 제공된 영어와 한글을 절대 변형하지 말고 그대로 사용하세요.
- 사용자가 영어만 제공한 경우: 직접 자연스러운 한국어로 번역하세요.

출력 형식

1. 문장별 영한 대조
영어 지문을 한 문장씩 나누고, 각 영어 문장 바로 아래에 한글 번역을 배치하세요.

형식:
영어 문장 1
한글 번역 1

영어 문장 2
한글 번역 2

(모든 문장에 대해 반복)

출력 순서 (각 문장마다 반복)
영어 문장
한글 번역
→ 핵심 어휘: 단어/표현 (한글 뜻) | 동의어/파생어: ... | 바꿔쓰기: ...

(다음 문장도 같은 형식으로 반복)

핵심 어휘 규칙
- 각 문장에서 중요한 단어/표현을 3개 이내로 선별
- 각 단어마다: 한글 뜻, 동의어 또는 파생어(있는 경우), 바꿔 쓸 수 있는 표현 2~3개(있는 경우)""" + NO_MARKDOWN,

    "quiz": """당신은 영어 시험 출제 전문가입니다. 아래 영어 지문을 바탕으로 다음 유형의 문제를 만드세요:

1. 어휘 문제 (3문제): 빈칸에 알맞은 단어 고르기
2. 내용 이해 문제 (3문제): 지문의 내용과 일치/불일치 판단
3. 추론 문제 (2문제): 지문에서 추론할 수 있는 내용
4. 어법 문제 (2문제): 밑줄 친 부분의 어법 판단

각 문제에 4개의 선택지와 정답 및 해설을 포함하세요.
문제와 선택지는 한국어로, 지문 인용 부분은 영어 원문 그대로 작성하세요.""" + NO_MARKDOWN,
}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/process", methods=["POST"])
def process():
    data = request.get_json()
    passages = data.get("passages", [])
    translations = data.get("translations", [])
    numbers = data.get("numbers", [])
    mode = data.get("mode", "translate")
    custom_prompt = data.get("customPrompt", "")

    if not passages:
        return jsonify({"error": "지문을 입력해주세요."}), 400

    system_prompt = PROMPTS.get(mode, custom_prompt)
    if not system_prompt:
        return jsonify({"error": "프롬프트를 입력해주세요."}), 400

    results = []
    for i, passage in enumerate(passages):
        if not passage.strip():
            continue

        label = numbers[i] if i < len(numbers) else str(i + 1)
        korean = translations[i] if i < len(translations) else ""
        if mode == "translate" and korean:
            user_content = f"[{label}번 지문]\n\n[영어]\n{passage}\n\n[한글 번역]\n{korean}"
        else:
            user_content = f"[{label}번 지문]\n\n{passage}"

        try:
            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_content}
                ],
            )
            results.append({
                "index": label,
                "passage": passage[:100] + "..." if len(passage) > 100 else passage,
                "result": message.content[0].text,
            })
        except Exception as e:
            results.append({
                "index": label,
                "passage": passage[:100] + "..." if len(passage) > 100 else passage,
                "result": f"오류 발생: {str(e)}",
            })

    # 자동 저장
    if results:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        mode_name = {"translate": "번역분석", "quiz": "문제생성", "custom": "커스텀"}.get(mode, mode)
        filename = f"{timestamp}_{mode_name}.txt"
        filepath = os.path.join(RESULTS_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            for r in results:
                f.write(f"{'='*60}\n")
                f.write(f"[{r['index']}번]\n")
                f.write(f"{'='*60}\n\n")
                f.write(r["result"])
                f.write("\n\n")

    return jsonify({"results": results})


@app.route("/review", methods=["POST"])
def review():
    data = request.get_json()
    passage = data.get("passage", "")
    translation = data.get("translation", "")
    analysis = data.get("analysis", "")
    label = data.get("label", "")

    if not passage or not analysis:
        return jsonify({"error": "검토할 데이터가 없습니다."}), 400

    review_prompt = """당신은 대한민국 영어 교육 검토 전문가입니다. 아래 분석본을 검토해주세요.

[검토 항목]

1. 원문 변형 여부
- 분석본에 인용된 영어 문장이 원문과 정확히 일치하는지 확인
- 한글 번역이 제공된 경우, 번역이 원본과 일치하는지 확인
- 변형된 부분이 있으면 구체적으로 지적

2. 어휘 난이도 검토
- 분석본에서 제시한 핵심 어휘, 동의어, 바꿔쓰기 표현의 난이도를 평가
- 각 단어/표현의 빈도 수준을 표시 (상: 수능 필수, 중: 수능 출제 가능, 하: 수능 범위 초과)
- 수능 영어 시험 수준(EBS 연계, 고등학교 교과서 기준)에 적합한지 판단
- 너무 어려운 단어가 있으면 수능 수준의 대체 표현 제안

3. 종합 평가
- 전체적인 분석 품질 한줄 평가
- 수정이 필요한 부분 요약

[중요] 출력 시 마크다운 문법(**, *, ##, ###, ``` 등)을 절대 사용하지 마세요. 순수 텍스트로만 작성하세요. 강조가 필요하면 대괄호[ ]나 화살표→를 사용하세요."""

    user_content = f"[{label}번 지문]\n\n[원문 영어]\n{passage}\n"
    if translation:
        user_content += f"\n[원문 한글 번역]\n{translation}\n"
    user_content += f"\n[분석본]\n{analysis}"

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=review_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        return jsonify({"review": message.content[0].text})
    except Exception as e:
        return jsonify({"error": f"검토 오류: {str(e)}"}), 500


@app.route("/upload-excel", methods=["POST"])
def upload_excel():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "파일을 선택해주세요."}), 400

    try:
        wb = openpyxl.load_workbook(io.BytesIO(file.read()))
        ws = wb.active
        passages = []
        translations = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            eng = str(row[0]).strip() if row[0] else ""
            kor = str(row[1]).strip() if len(row) > 1 and row[1] else ""
            if eng:
                passages.append(eng)
                translations.append(kor)
        return jsonify({"passages": passages, "translations": translations})
    except Exception as e:
        return jsonify({"error": f"엑셀 파일 읽기 오류: {str(e)}"}), 400


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
