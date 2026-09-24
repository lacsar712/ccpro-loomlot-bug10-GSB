"""染缸状态判定的唯一来源（single source of truth）。

后端的开立/移缸拦截与前端染程页下拉的可选集合必须同源：
都以 :data:`OPENABLE_VAT_STATUSES` 为准。排液（drain）后的染缸
不出现在可选集合中，后端接口也一律拒绝在其上开立或移入染程。
"""

from fastapi import HTTPException

# 可开立染程的染缸状态：就绪、染色中。排液 drain 不可开立。
OPENABLE_VAT_STATUSES = frozenset({"ready", "dyeing"})


def is_vat_openable(status: str) -> bool:
    """该状态的染缸是否可以开立/移入染程。"""
    return status in OPENABLE_VAT_STATUSES


def assert_openable(status: str) -> None:
    """校验失败时抛出与各开立入口一致的 409。"""
    if not is_vat_openable(status):
        raise HTTPException(
            status_code=409,
            detail=(
                f"染缸状态为「{status}」，仅 ready / dyeing 状态可开立染程"
            ),
        )
