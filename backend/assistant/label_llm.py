"""표/문단 항목명이 '그 회사를 대표하는 사람(대표자)'의 이름 칸인지 판별.

LangChain 체인(프롬프트 → 로컬 Qwen2.5-VL → 파서)으로 판단한다.
모델은 파이프라인이 이미 GPU 에 올려둔 (model, processor) 를 그대로 재사용한다
(별도 모델·API 키 없음).

3단계:
  1. 라벨에 '대표'가 들어있거나 알려진 동의어(사업주·경영주 등) → LLM 없이 True
  2. 담당자·연구원·보증인 등 명백히 대표가 아닌 라벨 → LLM 없이 False
  3. '성명·이름'처럼 문맥에 따라 달라지는 라벨만 → LLM 1회 호출(라벨+문맥 캐시)
     · 참여자명단·기술닥터·자기부담자 등 표는 아예 LLM 도 건너뜀(False)

models 가 없거나 추론 실패 시 None → 호출부(hwpx_fill._match_key)가 키워드 규칙으로 폴백.

is_ceo_label(label, context="", models=None) -> True | False | None
"""
from __future__ import annotations

import re

# 1) 라벨만 봐도 대표자 칸 (LLM 불필요)
_YES_RE = re.compile(
    r"대표|사업주|경영주|경영자|운영자|업주|점주|대표이사|대표자|공동대표|대표성명|대표명")
# 2) 라벨만 봐도 대표자 아님 (LLM 불필요)
_NOT_RE = re.compile(
    r"담당|실무|참여|책임|연구원|연대보증|보증인|입회|위원|간사|팀장|부서|기관장|"
    r"경리|회계|세무|배우자|주주|출자자|법인명|상호|회사명|기업명|업체명|기관명|단체명|"
    r"수급자|수혜자|추천")
# 3) 문맥에 따라 다른 '이름' 계열 라벨 → 여기 걸리면 LLM 에 물어봄
_NAME_RE = re.compile(r"^성명$|^성\s*명$|성함|이름|^명$")
# 표 전체에 이런 말이 있으면 '성명'은 대표자 칸이 아님 → LLM 도 건너뜀
_ROSTER_CTX = ("연번", "명단", "생년월일", "자기부담", "기술닥터", "참여인력",
               "참여연구원", "참여인원", "가족", "세대원", "종업원", "직원명")

_SYSTEM = (
    "너는 한국 정부지원사업 신청서의 표 항목명을 분류한다. "
    "항목명이 '그 사업체를 대표하는 사람(대표자·대표이사·개인사업자 본인)의 이름을 "
    "적는 칸'이면 Y, 아니면 N. 오직 Y 또는 N 한 글자만.\n"
    "예) 같은 줄에 '사업자등록번호·기업명·대표'가 있는 '성명' → Y\n"
    "예) 같은 줄에 '담당자·직위·연락처'가 있는 '성명' → N\n"
    "예) 같은 줄에 '연구원·소속·역할·기술닥터'가 있는 '성명' → N"
)
_HUMAN = "표 종류: {table}\n'{label}' 칸과 같은 줄: {row}\n답(Y/N):"

_CHAIN = None
_RESULT_CACHE: dict = {}
_DISABLED = False


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def _qwen_text(models, messages) -> str:
    import torch

    model, processor = models
    role_map = {"system": "system", "human": "user", "ai": "assistant", "user": "user"}
    msgs = [{"role": role_map.get(getattr(m, "type", "user"), "user"),
             "content": str(m.content)} for m in messages]
    text = processor.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    try:
        inputs = processor(text=[text], return_tensors="pt").to(model.device)
    except Exception:
        inputs = processor.tokenizer([text], return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=4, do_sample=False)
    gen = [o[len(i):] for i, o in zip(inputs.input_ids, out)]
    res = processor.batch_decode(gen, skip_special_tokens=True)[0]
    del inputs, out, gen
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return res


def _build_chain(models):
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.runnables import RunnableLambda

    prompt = ChatPromptTemplate.from_messages([("system", _SYSTEM), ("human", _HUMAN)])
    generate = RunnableLambda(lambda pv: _qwen_text(models, pv.to_messages()))
    return prompt | generate | StrOutputParser()


def is_ceo_label(label: str, context: str = "", models=None):
    """항목명이 대표자 이름 칸인지. True/False/None(판단보류→폴백).

    context: 그 항목이 있는 표(또는 같은 줄) 전체 텍스트.
    """
    global _CHAIN, _DISABLED

    s = _norm(label)
    if len(s) < 2:
        return None
    if _NOT_RE.search(s):
        return False
    if _YES_RE.search(s):
        return True
    if not _NAME_RE.search(s):
        return None  # '이름' 계열도 아님 → 폴백
    if any(w in context for w in _ROSTER_CTX):
        return False  # 명단·기술닥터·자기부담자 표의 '성명'은 대표자 아님
    if models is None or _DISABLED:
        return None

    row = _norm(context)[:60]
    ck = s + "|" + row
    if ck in _RESULT_CACHE:
        return _RESULT_CACHE[ck]
    try:
        if _CHAIN is None:
            _CHAIN = _build_chain(models)
        raw = _CHAIN.invoke({
            "label": label.strip(),
            "row": (context or "(없음)").strip()[:120],
            "table": (context or "(없음)").strip()[:80],
        })
        val = "Y" in (raw or "").upper()[:3]
        _RESULT_CACHE[ck] = val
        return val
    except Exception:
        _DISABLED = True
        return None


def reset_cache():
    global _CHAIN, _DISABLED
    _CHAIN = None
    _DISABLED = False
    _RESULT_CACHE.clear()
