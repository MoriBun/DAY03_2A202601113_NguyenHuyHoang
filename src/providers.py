"""
🔌 MULTI-PROVIDER LLM ADAPTER (OpenAI, Gemini, Anthropic, OpenRouter & Offline Mock)
Hỗ trợ chuyển đổi linh hoạt giữa các nhà cung cấp AI chỉ bằng cách đổi biến môi trường LLM_PROVIDER.
"""

import os
import sys
import json
import re
import requests
from dotenv import load_dotenv

# Đảm bảo in ra Tiếng Việt và Emojis không bị lỗi trên Windows Console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

load_dotenv()

class BaseLLMProvider:
    """Interface cơ sở cho tất cả các LLM Provider"""
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        raise NotImplementedError


class GeminiProvider(BaseLLMProvider):
    """Google Gemini Provider"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "gemini-2.5-flash"
        
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_gemini_api_key_here":
            return "[Gemini Error]: Chưa cấu hình GEMINI_API_KEY trong file .env!"
        try:
            from google import genai
            client = genai.Client(api_key=self.api_key)
            contents = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            response = client.models.generate_content(
                model=self.model_name,
                contents=contents
            )
            return response.text
        except Exception as e:
            return f"[Gemini Exception]: {str(e)}"


class OpenAIProvider(BaseLLMProvider):
    """OpenAI Provider (GPT-4o, GPT-3.5-turbo, etc.)"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "gpt-4o-mini"
        
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_openai_api_key_here":
            return "[OpenAI Error]: Chưa cấu hình OPENAI_API_KEY trong file .env!"
        try:
            import openai
            client = openai.OpenAI(api_key=self.api_key)
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = client.chat.completions.create(
                model=self.model_name,
                messages=messages
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"[OpenAI Exception]: {str(e)}"


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude Provider (Claude 3.5 Sonnet, Claude 3 Haiku)"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "claude-3-haiku-20240307"
        
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_anthropic_api_key_here":
            return "[Anthropic Error]: Chưa cấu hình ANTHROPIC_API_KEY trong file .env!"
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)
            kwargs = {
                "model": self.model_name,
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}]
            }
            if system_prompt:
                kwargs["system"] = system_prompt
                
            response = client.messages.create(**kwargs)
            return response.content[0].text
        except Exception as e:
            return f"[Anthropic Exception]: {str(e)}"


class OpenRouterProvider(BaseLLMProvider):
    """OpenRouter Provider (Hỗ trợ gọi mọi model qua OpenRouter API)"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "google/gemini-2.5-flash"
        
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_openrouter_api_key_here":
            return "[OpenRouter Error]: Chưa cấu hình OPENROUTER_API_KEY trong file .env!"
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            payload = {
                "model": self.model_name,
                "messages": messages
            }
            res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=30)
            if res.status_code == 200:
                data = res.json()
                return data["choices"][0]["message"]["content"]
            else:
                return f"[OpenRouter API Error {res.status_code}]: {res.text}"
        except Exception as e:
            return f"[OpenRouter Exception]: {str(e)}"


class MockProvider(BaseLLMProvider):
    """Offline Mock Provider (Cho bài test không cần kết nối API)"""
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        text = prompt.lower()
        system_text = system_prompt.lower()

        if "jd:" in text and "ứng viên:" in text:
            match = re.search(r"current_test_case_id:\s*(\d+)", system_text)
            if "không có khả năng truy cập cơ sở dữ liệu" in system_text:
                return (
                    "Dựa trên JD và hồ sơ bạn đã cung cấp, HR nên đối chiếu chức danh, kỹ năng, "
                    "kinh nghiệm, lĩnh vực và địa điểm; cần xác minh các bằng chứng trước khi đưa ra quyết định."
                )
            if match:
                test_case_id = match.group(1)
                if "observation: 📊 điểm sàng lọc" in text:
                    return (
                        "Thought: Tôi đã nhận được điểm từ công cụ chấm điểm.\n"
                        "Final Answer: Điểm sàng lọc đã được tổng hợp bên dưới để HR tham khảo; "
                        "hãy xác minh bằng CV gốc và phỏng vấn trước khi quyết định."
                    )
                return (
                    "Thought: Cần gọi công cụ chấm điểm trước khi đưa ra nhận xét.\n"
                    f"Action: score_test_case[{test_case_id}]"
                )
            return (
                "Thought: JD và hồ sơ đã có sẵn trong câu hỏi, nên không cần gọi tool.\n"
                "Final Answer: Ứng viên có một số điểm phù hợp để HR xem xét sơ bộ. "
                "Hãy đối chiếu chức danh, kỹ năng, kinh nghiệm, lĩnh vực và địa điểm với JD, "
                "sau đó kiểm chứng bằng CV gốc và phỏng vấn trước khi quyết định."
            )

        if "testcaseid:" in text:
            match = re.search(r"testcaseid:\s*(\d+)", text)
            test_case_id = match.group(1) if match else ""
            if "không có khả năng truy cập cơ sở dữ liệu" in system_text:
                return "Xin lỗi, tôi chưa có quyền truy cập dữ liệu JD và hồ sơ của test case này."
            if "observation:" in text and "test_case_id" in text:
                return (
                    "Thought: Tôi đã có JD và hồ sơ từ tool để đưa ra nhận xét hỗ trợ HR.\n"
                    "Final Answer: Hãy đối chiếu chức danh, kỹ năng, kinh nghiệm, lĩnh vực và địa điểm; "
                    "chỉ mời phỏng vấn khi bằng chứng trong hồ sơ đáp ứng các tiêu chí liên quan đến công việc."
                )
            return (
                "Thought: Cần lấy dữ liệu JD và hồ sơ của test case trước khi đánh giá.\n"
                f"Action: get_test_case_data[{test_case_id}]"
            )
        if "thời tiết" in text and "hà nội" in text:
            return "Thought: Cần tra cứu thời tiết Hà Nội.\nAction: get_weather['Hà Nội']"
        return "🤖 [Mock Provider]: Phản hồi giả lập offline cho bài test."


def get_llm_provider(provider_name: str = None) -> BaseLLMProvider:
    """Factory function tự chọn Provider từ biến môi trường LLM_PROVIDER"""
    name = (provider_name or os.getenv("LLM_PROVIDER") or "mock").lower().strip()
    
    if name == "gemini":
        return GeminiProvider()
    elif name == "openai":
        return OpenAIProvider()
    elif name == "anthropic":
        return AnthropicProvider()
    elif name == "openrouter":
        return OpenRouterProvider()
    else:
        return MockProvider()


if __name__ == "__main__":
    print("=== TEST MULTI-PROVIDER LLM ADAPTER ===")
    provider = get_llm_provider()
    print(f"✅ Provider đang dùng: {provider.__class__.__name__}")
    print(f"🤖 User Query: Hello")
    print(f"💬 Response  : {provider.generate('Hello')}")
