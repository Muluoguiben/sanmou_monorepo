import io,json,struct,tempfile,zlib
from pathlib import Path
from PIL import Image
from fastapi.testclient import TestClient
from pioneer_agent.app.advisor_api import AdvisorApiService,create_app

def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
payload=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',20000,20000,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\0\0\0\0'))+chunk(b'IEND',b'')
assert Image.MAX_IMAGE_PIXELS is not None
try:Image.open(io.BytesIO(payload))
except Image.DecompressionBombError:pass
else:raise AssertionError('Pillow guard did not reject header; do not decode')
with tempfile.TemporaryDirectory() as tmp:
 service=AdvisorApiService(data_dir=Path(tmp),default_mock_mode=True)
 with TestClient(create_app(service),raise_server_exceptions=False) as client:
  response=client.post('/api/advisor/analyze',files={'screenshot':('synthetic-pixel-limit.png',payload,'image/png')})
 remaining=list(service.upload_dir.iterdir())
 print(json.dumps({'input_bytes':len(payload),'pillow_guard':'DecompressionBombError before pixel decoding','http_status':response.status_code,'remaining_upload_count':len(remaining),'remaining_bytes':sum(p.stat().st_size for p in remaining),'report_written':service.report_log.exists()}))
 assert response.status_code in {400,413} and not remaining,'image validation guard leaves uploaded file'
