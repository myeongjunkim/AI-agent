# Test Cases

## DART MCP Server Test

### 1. M&A Disclosure Query Test

Query for merger ratios in recent M&A disclosures:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/chat/" \
  -H "Content-Type: application/json; charset=utf-8" \
  -d '"최근 1개월 상장회사의 인수 합병 공시에서 합병 비율은 어땠는지 찾아봐줘."'
```

### 2. Alternative Test (English)

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/chat/" \
  -H "Content-Type: application/json" \
  -d '{"message": "Find merger ratios in recent M&A disclosures from the past month"}'
```

### 3. Additional Test Cases

More test cases to be added...