import argparse
import os
import uvicorn


def main():
    parser=argparse.ArgumentParser(description='Run the SmartMove synthetic operations platform.')
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=8501)
    args=parser.parse_args()
    print(f'\nSmartMove • http://localhost:{args.port}\nSynthetic operational prototype. Press Ctrl+C to stop.\n',flush=True)
    if args.host not in ('127.0.0.1','localhost') and os.getenv('SMARTMOVE_ENV')!='production':
        print('WARNING: Local demo mode is being exposed beyond loopback. Use only on a trusted network. Never expose this edition directly to the internet.',flush=True)
    uvicorn.run('smartmove.app:app',host=args.host,port=args.port,access_log=False)


if __name__=='__main__':main()
