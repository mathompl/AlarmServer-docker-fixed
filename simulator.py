import socket
import threading
import time

HOST = '127.0.0.1'
PORT = 4026

def handle_client(conn, addr):
    print(f"[SIM] Połączono z {addr}")
    conn.sendall(b"505000\r\n")   # Login request

    try:
        while True:
            data = conn.recv(1024)
            if not data:
                print(f"[SIM] Klient zamknął połączenie")
                break

            msg = data.decode().strip()
            print(f"[SIM] Otrzymano: {msg}")

            if msg.startswith("000"):
                print("[SIM] Keepalive received → sending 500")
                conn.sendall(b"500\r\n")

            elif msg.startswith("001"):
                print("[SIM] Status request")
                conn.sendall(b"00100\r\n")

            # Nie zamykamy połączenia po odpowiedzi!
            time.sleep(0.1)

    except Exception as e:
        print(f"[SIM] Błąd: {e}")
    finally:
        conn.close()
        print(f"[SIM] Rozłączono {addr}")


def start_simulator():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(5)
    print(f"[SIM] Symulator Envisalink działa na {HOST}:{PORT}")

    while True:
        conn, addr = server.accept()
        thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        thread.start()


if __name__ == "__main__":
    start_simulator()
