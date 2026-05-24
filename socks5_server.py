#!/usr/bin/env python3
import socket, threading, sys

PORT = 7890  # 换一个不冲突的端口

def forward(src, dst):
    try:
        while True:
            data = src.recv(4096)
            if not data:
                break
            dst.send(data)
    except:
        pass
    finally:
        try: src.close()
        except: pass
        try: dst.close()
        except: pass

def handle(client):
    try:
        # SOCKS5握手
        data = client.recv(262)
        client.send(b'\x05\x00')  # 无需认证
        
        # 接收请求
        data = client.recv(262)
        if len(data) < 7:
            return
        
        cmd = data[1]
        atyp = data[3]
        
        if atyp == 1:  # IPv4
            host = socket.inet_ntoa(data[4:8])
            port = int.from_bytes(data[8:10], 'big')
        elif atyp == 3:  # 域名
            host_len = data[4]
            host = data[5:5+host_len].decode('utf-8')
            port = int.from_bytes(data[5+host_len:7+host_len], 'big')
        else:
            return
        
        # 连接目标
        server = socket.create_connection((host, port), timeout=10)
        client.send(b'\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00')
        
        # 双向转发
        t1 = threading.Thread(target=forward, args=(client, server), daemon=True)
        t2 = threading.Thread(target=forward, args=(server, client), daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        
    except Exception as e:
        try: client.close()
        except: pass

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('0.0.0.0', PORT))
    s.listen(128)
    print(f'✅ SOCKS5服务器启动成功，监听端口 {PORT}')
    print(f'   在SocksDroid里填写:')
    print(f'   Server IP: 192.168.1.3')
    print(f'   Server Port: {PORT}')
    print(f'   按 Ctrl+C 停止')
    
    while True:
        try:
            client, addr = s.accept()
            threading.Thread(target=handle, args=(client,), daemon=True).start()
        except KeyboardInterrupt:
            print('\n停止服务器')
            break
        except Exception as e:
            pass

if __name__ == '__main__':
    main()
