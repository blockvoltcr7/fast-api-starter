from mangum import Mangum
from api.s3_api import app

handler = Mangum(app)
