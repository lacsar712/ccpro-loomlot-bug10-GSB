"""染缸状态与「可开立染程」判定的唯一来源。

后端拦截、GET /vats 过滤以及前端下拉都必须以这里的 OPENABLE_VAT_STATUSES
为准，避免各处各写一份导致排液缸仍可开立。
"""

VAT_STATUS_READY = "ready"
VAT_STATUS_DYEING = "dyeing"
VAT_STATUS_DRAIN = "drain"

# 可开立染程的染缸状态（有序，仅用于错误文案；同时可直接用于 SQL IN 过滤）。
# 新增/调整可开缸状态时只改这里。
OPENABLE_VAT_STATUSES = (VAT_STATUS_READY, VAT_STATUS_DYEING)


def vat_openable(status: str | None) -> bool:
    """该状态的染缸当前是否可开立染程。"""
    return status in OPENABLE_VAT_STATUSES
