import os
from flask import Flask, render_template, request, jsonify
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

PROMPTS = {
    "translate": """당신은 영어 교육 전문가입니다. 아래 영어 지문에 대해 다음 작업을 수행하세요:

1. **한국어 번역**: 자연스러운 한국어로 번역
2. **핵심 어휘**: 중요 단어/숙어 10개를 선별하여 뜻과 예문 제공
3. **문법 분석**: 주요 문법 포인트 3-5개 설명
4. **구문 분석**: 복잡한 문장 구조 해설

각 섹션을 명확히 구분하여 작성하세요.""",

    "quiz": """당신은 영어 시험 출제 전문가입니다. 아래 영어 지문을 바탕으로 다음 유형의 문제를 만드세요:

1. **어휘 문제** (3문제): 빈칸에 알맞은 단어 고르기
2. **내용 이해 문제** (3문제): 지문의 내용과 일치/불일치 판단
3. **추론 문제** (2문제): 지문에서 추론할 수 있는 내용
4. **어법 문제** (2문제): 밑줄 친 부분의 어법 판단

각 문제에 4개의 선택지와 정답 및 해설을 포함하세요.
문제와 선택지는 한국어로, 지문 인용 부분은 영어 원문 그대로 작성하세요.""",
}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/process", methods=["POST"])
def process():
    data = request.get_json()
    passages = data.get("passages", [])
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
        try:
            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": f"[지문 {i + 1}]\n\n{passage}"}
                ],
            )
            results.append({
                "index": i + 1,
                "passage": passage[:100] + "..." if len(passage) > 100 else passage,
                "result": message.content[0].text,
            })
        except Exception as e:
            results.append({
                "index": i + 1,
                "passage": passage[:100] + "..." if len(passage) > 100 else passage,
                "result": f"오류 발생: {str(e)}",
            })

    return jsonify({"results": results})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
