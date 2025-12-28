import socket
import threading

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # 监听 0.0.0.0 确保外网可连，端口可自定义
    server.bind(('0.0.0.0', 8888))
    server.listen(10)
    print("匹配服务器已启动，监听端口 8888...")

    waiting_player = None # 存储 (socket, addr)

    while True:
        conn, addr = server.accept()
        print(f"新连接: {addr}")
        
        if waiting_player is None:
            waiting_player = (conn, addr)
            conn.send("WAIT".encode()) # 通知玩家正在等待
        else:
            # 撮合成功
            peer_conn, peer_addr = waiting_player
            try:
                # 互相告知对方的外网IP
                # 格式: MATCH:IP_ADDRESS:ROLE (ROLE: 1为房主, 0为加入者)
                peer_conn.send(f"MATCH:{addr[0]}:1".encode()) 
                conn.send(f"MATCH:{peer_addr[0]}:0".encode())
            except:
                print("匹配对象已断开，重新入队")
            
            peer_conn.close()
            conn.close()
            waiting_player = None

if __name__ == "__main__":
    start_server()