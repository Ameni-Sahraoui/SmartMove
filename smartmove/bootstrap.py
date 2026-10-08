from .seed import generate
from .security import bootstrap
from .config import DATA

if __name__=='__main__':
    generate()
    bootstrap()
    print(f'Credentials file: {DATA / "LOCAL_CREDENTIALS.txt"}')
