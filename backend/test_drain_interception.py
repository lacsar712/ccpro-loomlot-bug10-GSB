"""排液后开立拦截与前后端同源数据的端到端校验（sqlite + TestClient）。

覆盖：
- GET /vats 下发 openable，且 ready/dyeing=true、drain=false（与后端拦截同源）。
- POST /dye-lots：drain 缸一律 409，配方名含「补」也不放行；ready 缸 201 并转 dyeing。
- PUT /dye-lots：移入 drain 缸 409；不换缸编辑其他字段 200。
- 排液流程：POST /vats/{id}/drain 后，GET 状态/徽章源(status,openable) 立即变更，
  随后开立被拒；与“刷新前”行为一致（无任何前端缓存参与判定）。
"""

import os
import tempfile

# 必须在导入 app 之前指定 sqlite 数据库
_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine, get_db  # noqa: E402
from app.auth import get_current_user  # noqa: E402
from app.main import app  # noqa: E402
from app.models.dye_house import DyeHouse  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.vat import Vat  # noqa: E402

Base.metadata.create_all(bind=engine)

# 鉴权旁路：测试不签发真实 JWT
app.dependency_overrides[get_current_user] = lambda: User(
    id=1, username="tester", role="admin", hashed_password="x"
)

client = TestClient(app)


def setup_vats():
    db = SessionLocal()
    try:
        if db.query(DyeHouse).count() == 0:
            h = DyeHouse(name="测试坊", water_note="", notes="")
            db.add(h)
            db.flush()
            db.add_all(
                [
                    Vat(dye_house_id=h.id, vat_code="READY", fiber_type="棉",
                        capacity_l=100, status="ready"),
                    Vat(dye_house_id=h.id, vat_code="DYEING", fiber_type="棉",
                        capacity_l=100, status="dyeing"),
                    Vat(dye_house_id=h.id, vat_code="DRAIN", fiber_type="棉",
                        capacity_l=100, status="drain"),
                ]
            )
            db.commit()
        return {v.vat_code: v.id for v in db.query(Vat).all()}
    finally:
        db.close()


IDS = setup_vats()
LOT_PAYLOAD_TMPL = {
    "recipeName": "靛蓝冷染",
    "fabricKg": 20,
    "startedAt": "2026-09-24T08:00:00",
    "operatorName": "操作员",
}
failures = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


# 1) openable 标志同源下发
r = client.get("/api/vats")
check("GET /vats 200", r.status_code == 200, r.text)
by_code = {v["vatCode"]: v for v in r.json()}
check("ready.openable is True", by_code["READY"]["openable"] is True)
check("dyeing.openable is True", by_code["DYEING"]["openable"] is True)
check("drain.openable is False", by_code["DRAIN"]["openable"] is False)
check("drain.status == drain", by_code["DRAIN"]["status"] == "drain")

# 2) POST 在 drain 缸被拒（普通配方名）
r = client.post("/api/dye-lots", json={**LOT_PAYLOAD_TMPL, "vatId": IDS["DRAIN"]})
check("POST on drain (normal recipe) -> 409", r.status_code == 409, r.text)

# 3) POST 在 drain 缸被拒（配方名含「补」——旧埋点放行路径必须封死）
r = client.post(
    "/api/dye-lots",
    json={**LOT_PAYLOAD_TMPL, "vatId": IDS["DRAIN"], "recipeName": "补染配方"},
)
check("POST on drain (recipe 补) -> 409", r.status_code == 409, r.text)

# 4) POST 在 ready 缸成功且状态转 dyeing
r = client.post("/api/dye-lots", json={**LOT_PAYLOAD_TMPL, "vatId": IDS["READY"]})
check("POST on ready -> 201", r.status_code == 201, r.text)
lot_id = r.json()["id"]
r = client.get(f"/api/vats/{IDS['READY']}")
check("ready vat flipped to dyeing", r.json()["status"] == "dyeing", r.text)

# 5) 排液流程：把 READY（现 dyeing）缸排液后，开立必须被拒，且徽章源立即变更
r = client.post(f"/api/vats/{IDS['READY']}/drain")
check("drain -> 200 + status drain", r.status_code == 200 and r.json()["status"] == "drain", r.text)
check("drain response openable False", r.json()["openable"] is False, r.text)
r = client.get(f"/api/vats/{IDS['READY']}")
check("refetch still drain (refresh-invariant)", r.json()["status"] == "drain"
      and r.json()["openable"] is False, r.text)
r = client.post("/api/dye-lots", json={**LOT_PAYLOAD_TMPL, "vatId": IDS["READY"]})
check("POST after drain -> 409", r.status_code == 409, r.text)

# 6) PUT 移缸：移入 drain 缸被拒
r = client.post("/api/dye-lots", json={**LOT_PAYLOAD_TMPL, "vatId": IDS["DYEING"]})
# DYEING 缸已用于开立，可继续；若上面失败则用 lot_id 自身做“不换缸”对照
moving_lot = r.json()["id"] if r.status_code == 201 else lot_id
r = client.put(f"/api/dye-lots/{moving_lot}", json={"vatId": IDS["DRAIN"]})
check("PUT move onto drain -> 409", r.status_code == 409, r.text)

# 7) PUT 不换缸、仅改配方名 -> 200（排液缸上的存量染程仍可编辑非缸字段）
r = client.put(f"/api/dye-lots/{lot_id}", json={"recipeName": "改名不改缸"})
check("PUT same vat other fields -> 200", r.status_code == 200, r.text)

# 8) 列表与拦截同源：可开立集合(openable=true)恰好是后端接受开立的缸
r = client.get("/api/vats")
openable_ids = {v["id"] for v in r.json() if v["openable"]}
accepted = set()
for vid in [IDS["READY"], IDS["DYEING"], IDS["DRAIN"]]:
    resp = client.post(
        "/api/dye-lots",
        json={**LOT_PAYLOAD_TMPL, "vatId": vid, "recipeName": "同源探测"},
    )
    if resp.status_code == 201:
        accepted.add(vid)
check("selectable set == backend-accepted set", openable_ids == accepted,
      f"openable={openable_ids} accepted={accepted}")

print()
if failures:
    print(f"{len(failures)} FAILURE(S): {failures}")
    raise SystemExit(1)
print("ALL CHECKS PASSED")
