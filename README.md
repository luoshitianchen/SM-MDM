# SM MDM

主数据管理：员工、部门、客户、供应商和产品统一编码。

```powershell
git clone https://github.com/luoshitianchen/SM-MDM.git
cd SM-MDM
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8450
```

接口：`/health`、`/readyz`、`/api/overview`、`/api/items`、`/api/ops/metrics`、`/api/crypto/status`。

内置 TrustedHost、安全响应头、CSP、国密状态接口和容器加固。
