"""Role 4 application entry point for the Chatbot Baseline and ReAct Agent."""

import json
import os
import sys

from dotenv import load_dotenv


SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

from agent_core import run_react_agent as run_react_loop
from prompts import CHATBOT_BASELINE_PROMPT, MAX_ITERATIONS, REACT_SYSTEM_PROMPT
from providers import get_llm_provider
from tools import AVAILABLE_TOOLS

load_dotenv()


def load_test_cases():
    """Load either a JSON list or an object containing a ``test_cases`` list."""
    config_path = os.path.join(os.path.dirname(SRC_DIR), "config", "test_cases.json")
    with open(config_path, "r", encoding="utf-8") as file:
        payload = json.load(file)

    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("test_cases"), list):
        return payload["test_cases"]
    raise ValueError("config/test_cases.json phải là list hoặc có khóa 'test_cases' dạng list.")


def format_test_case_query(test_case: dict) -> str:
    """Create an agent query from either a natural-language or structured case."""
    question = test_case.get("question")
    if isinstance(question, str) and question.strip():
        return question.strip()

    if isinstance(test_case.get("JD"), dict) and isinstance(test_case.get("candidate"), dict):
        return (
            "Hãy đánh giá mức độ phù hợp của ứng viên với vị trí tuyển dụng dưới đây. "
            "Nêu điểm mạnh, điểm cần xác minh thêm và khuyến nghị để HR xem xét; "
            "không tự động đưa ra quyết định tuyển dụng.\n\n"
            f"JD: {json.dumps(test_case['JD'], ensure_ascii=False)}\n"
            f"Ứng viên: {json.dumps(test_case['candidate'], ensure_ascii=False)}"
        )
    raise ValueError(f"Test case id={test_case.get('id', '?')} thiếu dữ liệu cần thiết.")


def run_baseline_chatbot(user_query: str, provider):
    """Run exactly one provider call without registering or calling tools."""
    print(f"\n💬 [CHATBOT BASELINE] Câu hỏi: {user_query}")
    response = provider.generate(user_query, system_prompt=CHATBOT_BASELINE_PROMPT).strip()
    print(f"🤖 Chatbot trả lời:\n{response}")
    return {"answer": response, "tool_calls": 0}


def format_scorecard(test_case: dict | None) -> str:
    """Render Role 1's structured score breakdown for HR review."""
    if not test_case or not isinstance(test_case.get("expected_score_breakdown"), dict):
        return ""

    labels = {
        "preferred_title": "Chức danh mong muốn",
        "skills_and_tasks": "Kỹ năng & nhiệm vụ",
        "work_experience": "Kinh nghiệm làm việc",
        "domain_fit": "Phù hợp lĩnh vực",
        "location_fit": "Phù hợp địa điểm",
    }
    score = test_case["expected_score_breakdown"]
    lines = ["📊 ĐIỂM SÀNG LỌC ỨNG VIÊN (hỗ trợ HR):"]
    for key, maximum in (("preferred_title", 15), ("skills_and_tasks", 40), ("work_experience", 30), ("domain_fit", 10), ("location_fit", 5)):
        lines.append(f"- {labels[key]}: {score.get(key, 0)}/{maximum}")

    total = test_case.get("expected_total_100", sum(score.values()))
    grade = test_case.get("expected_grade", round(float(total) / 10, 1))
    lines.extend(
        [
            f"- Tổng điểm: {total}/100 ({grade}/10)",
            "Lưu ý: Điểm chỉ hỗ trợ HR xem xét; quyết định mời phỏng vấn cần kiểm tra CV gốc và bằng chứng liên quan đến công việc.",
        ]
    )
    return "\n".join(lines)


def build_scoring_tool(test_cases: list[dict]):
    """Create a read-only scoring tool backed by Role 1's grading fixtures."""
    cases_by_id = {str(test_case.get("id")): test_case for test_case in test_cases}

    def score_test_case(test_case_id: str) -> str:
        """Return the screening scorecard for one TestCaseID."""
        test_case = cases_by_id.get(str(test_case_id).strip())
        if test_case is None:
            return f"LỖI: Không tìm thấy TestCaseID '{test_case_id}'."
        scorecard = format_scorecard(test_case)
        return scorecard or f"LỖI: TestCaseID '{test_case_id}' không có dữ liệu chấm điểm."

    return {"score_test_case": score_test_case}


def run_react_agent(user_query: str, provider, test_case: dict | None = None):
    """Integrate Role 1 data, Role 2 tools, Role 3 prompt and the ReAct core."""
    tools = dict(AVAILABLE_TOOLS)
    system_prompt = REACT_SYSTEM_PROMPT
    if test_case and test_case.get("expected_score_breakdown"):
        test_case_id = str(test_case["id"])
        tools.update(build_scoring_tool([test_case]))
        system_prompt += (
            "\n\nTOOL CHẤM ĐIỂM (bắt buộc cho test case hiện tại):\n"
            "score_test_case[test_case_id]: Trả điểm sàng lọc theo rubric. "
            f"CURRENT_TEST_CASE_ID: {test_case_id}. Gọi score_test_case[{test_case_id}] trước Final Answer."
        )

    print(f"\n🤖 [REACT AGENT] Câu hỏi: {user_query}")
    print(f"🛠️ Agent đang có {len(tools)} tool: {', '.join(tools)}")
    print(f"🛡️ Guardrail: tối đa {MAX_ITERATIONS} vòng lặp")

    result = run_react_loop(user_query, provider, tools, system_prompt, MAX_ITERATIONS)
    for item in result["trace"]:
        print(f"\n--- 🔄 Vòng lặp ReAct (Step {item['step']}/{MAX_ITERATIONS}) ---")
        if item.get("thought"):
            print(f"🧠 Thought: {item['thought']}")
        if item.get("kind") == "parse_error":
            print(f"⚠️ Parse error: {item['observation']}")
            continue
        print(f"🛠️ Action: {item['name']}[{', '.join(item['arguments'])}]")
        print(f"👁️ Observation: {item['observation']}")

    if result["termination_reason"] == "max_iterations":
        print(f"\n🛡️ GUARDRAIL TRIGGERED: Đã đạt giới hạn {MAX_ITERATIONS} vòng lặp.")
    elif result["termination_reason"] == "parse_error":
        print("\n🛡️ GUARDRAIL TRIGGERED: Dừng sau 2 phản hồi sai định dạng liên tiếp.")
    scorecard = format_scorecard(test_case)
    scoring_tool_called = any(item.get("name") == "score_test_case" for item in result["trace"])
    if scorecard and not scoring_tool_called:
        result["answer"] = f"{result['answer']}\n\n{scorecard}"
    print(f"\n🏁 Final Answer: {result['answer']}")
    print(f"📊 Tool calls: {result['tool_calls']}")
    return result


def run_all_test_cases(test_cases: list[dict], provider):
    """Run every structured applicant case and print an individual scorecard."""
    for test_case in test_cases:
        print("\n" + "=" * 50)
        print(f"TEST CASE #{test_case.get('id', '?')}: {test_case.get('category', '')}")
        query = format_test_case_query(test_case)
        run_baseline_chatbot(query, provider)
        run_react_agent(query, provider, test_case)


if __name__ == "__main__":
    print("=" * 50)
    print("🏫 ĐẠI HỌC VINUNI - BÀI LAB 3: CHATBOT VS REACT AGENT")
    print("=" * 50)

    provider = get_llm_provider()
    model_name = getattr(provider, "model_name", "Offline Mock Mode")
    print(f"🔌 LLM Provider đang hoạt động: {provider.__class__.__name__} (Model: {model_name})")

    tests = load_test_cases()
    print(f"✅ Đã tải thành công {len(tests)} Test Cases từ config/test_cases.json")
    if "--all" in sys.argv:
        run_all_test_cases(tests, provider)
    else:
        sample = next((test_case for test_case in tests if test_case.get("id") == 3), tests[0])
        sample_query = format_test_case_query(sample)

        print("\n--- DEMO 1: CHẠY TRÊN CHATBOT BASELINE ---")
        run_baseline_chatbot(sample_query, provider)
        print("\n--- DEMO 2: CHẠY TRÊN REACT AGENT ---")
        run_react_agent(sample_query, provider, sample)
