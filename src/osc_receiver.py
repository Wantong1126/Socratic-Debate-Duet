from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer


HOST = "127.0.0.1"
PORT = 9000


def show_message(address, *values):
    formatted_values = ", ".join(
        f"{value:.3f}"
        if isinstance(value, float)
        else str(value)
        for value in values
    )

    print(f"{address} | {formatted_values}")


dispatcher = Dispatcher()
dispatcher.set_default_handler(show_message)

server = ThreadingOSCUDPServer(
    (HOST, PORT),
    dispatcher,
)

print(f"Listening for OSC at udp://{HOST}:{PORT}")
print("Press Ctrl+C to stop.")

try:
    server.serve_forever()
except KeyboardInterrupt:
    print("\nOSC receiver stopped.")
finally:
    server.server_close()