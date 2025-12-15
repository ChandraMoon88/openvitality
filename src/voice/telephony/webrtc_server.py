import asyncio
import logging
import json
import os
from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer
from aiortc.contrib.media import MediaPlayer, MediaRecorder
from aiortc.rtcrtpsender import RTCRtpSender
from aiortc.rtcicetransport import RTCIceGatherer, RTCIceTransport, RTCIceCandidate

logger = logging.getLogger(__name__)

# Dictionary to hold active peer connections
pcs = set()

# Configuration for STUN/TURN servers
# Google's public STUN servers are widely used for NAT traversal
STUN_SERVERS = os.getenv("WEBRTC_STUN_SERVERS", "stun:stun.l.google.com:19302,stun:stun1.l.google.com:19302").split(',')
# TURN servers would require credentials and usually cost money, so omitted for basic free setup

class WebRTCServer:
    def __init__(self, host='0.0.0.0', port=8080, on_track_received=None, on_data_channel_message=None):
        self.host = host
        self.port = port
        self.app = web.Application()
        self.app.router.add_post("/offer", self.offer)
        self.app.router.add_static("/", ".") # Serve static files (e.g., a simple HTML client)
        self.on_track_received = on_track_received
        self.on_data_channel_message = on_data_channel_message

        # WebRTC Configuration
        ice_servers = [RTCIceServer(url) for url in STUN_SERVERS]
        self.rtc_configuration = RTCConfiguration(ice_servers)
        logger.info(f"WebRTC server initialized with STUN servers: {STUN_SERVERS}")

    async def offer(self, request):
        params = await request.json()
        offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

        pc = RTCPeerConnection(self.rtc_configuration)
        pcs.add(pc)

        player = None # Placeholder for media player if we want to send pre-recorded media
        recorder = None # Placeholder for media recorder if we want to record the call

        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            logger.info("Connection state is %s", pc.connectionState)
            if pc.connectionState == "closed":
                logger.info("Connection closed, removing peer connection.")
                if recorder:
                    await recorder.stop()
                pcs.discard(pc)

        @pc.on("track")
        def on_track(track):
            logger.info("Track %s received", track.kind)
            if self.on_track_received:
                self.on_track_received(track, pc) # Callback for AI to process audio/video

            if track.kind == "audio":
                # For now, let's just log audio activity or pass to a placeholder
                logger.info("Audio track received. (Placeholder for STT integration)")
                # Example: You might record it, or feed it to an STT engine
                # recorder = MediaRecorder("received_audio.wav") # Example recording
                # recorder.addTrack(track)
                # asyncio.create_task(recorder.start())
            elif track.kind == "video":
                # Placeholder for video processing
                logger.info("Video track received. (Placeholder for video AI integration)")
                # recorder = MediaRecorder("received_video.webm") # Example recording
                # recorder.addTrack(track)
                # asyncio.create_task(recorder.start())

        @pc.on("datachannel")
        def on_datachannel(channel):
            logger.info("Data channel '%s'-'%s' created", channel.label, channel.protocol)

            @channel.on("message")
            def on_message(message):
                logger.info("Data channel message: %s", message)
                if self.on_data_channel_message:
                    self.on_data_channel_message(message, pc, channel)
                
                # Echo message back (example)
                # channel.send("Echo: " + message)

        # Set the remote description and create an answer
        await pc.setRemoteDescription(offer)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        return web.Response(
            content_type="application/json",
            text=json.dumps({"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}),
        )

    async def start_server(self):
        logger.info(f"Starting WebRTC server on http://{self.host}:{self.port}")
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        logger.info("WebRTC server running.")
        try:
            while True:
                await asyncio.sleep(3600)  # Keep serving forever
        except asyncio.CancelledError:
            pass
        finally:
            await runner.cleanup()
            logger.info("WebRTC server stopped.")

    async def shutdown(self):
        logger.info("Shutting down WebRTC server and closing all peer connections...")
        # Close all peer connections
        coros = [pc.close() for pc in pcs]
        await asyncio.gather(*coros)
        pcs.clear()
        logger.info("All peer connections closed.")


# Example usage
async def main():
    logging.basicConfig(level=logging.INFO)

    def my_on_track_received(track, peer_connection):
        logger.info(f"Custom handler: Received {track.kind} track from {peer_connection.remoteDescription.type} connection.")
        # Here you would typically feed audio tracks to your STT engine
        # and process video tracks.
        # For audio, you might instantiate an aiortc.contrib.media.MediaRecorder
        # For video, similar approach or pass to a video processing pipeline.
        if track.kind == "audio":
            logger.info("Feeding audio track to a hypothetical STT pipeline...")
            # Example: A custom audio sink could be created here
            # that feeds audio frames to your STT service.
            pass
        elif track.kind == "video":
            logger.info("Feeding video track to a hypothetical video AI pipeline...")
            pass

    def my_on_data_channel_message(message, peer_connection, data_channel):
        logger.info(f"Custom handler: Data channel message '{message}' from {peer_connection.remoteDescription.type} connection.")
        # Respond via data channel
        data_channel.send(f"Server received: {message}")

    server = WebRTCServer(
        host='0.0.0.0',
        port=8080,
        on_track_received=my_on_track_received,
        on_data_channel_message=my_on_data_channel_message
    )

    try:
        await server.start_server()
    except KeyboardInterrupt:
        logger.info("Server interrupted by user.")
    finally:
        await server.shutdown()

if __name__ == "__main__":
    # To run this example, you would also need an HTML client
    # that sends an SDP offer to http://localhost:8080/offer
    # and handles the SDP answer.
    # A simple client might look like:
    # <script>
    #   async function call() {
    #     const pc = new RTCPeerConnection();
    #     pc.addTransceiver('audio', {'direction': 'sendrecv'});
    #     pc.addTransceiver('video', {'direction': 'sendrecv'});
    #     const dc = pc.createDataChannel("chat");
    #     dc.onmessage = e => console.log("DC:", e.data);
    #
    #     await pc.setLocalDescription(await pc.createOffer());
    #     const response = await fetch('/offer', {
    #       method: 'POST',
    #       headers: {'Content-Type': 'application/json'},
    #       body: JSON.stringify({sdp: pc.localDescription.sdp, type: pc.localDescription.type})
    #     });
    #     const answer = await response.json();
    #     await pc.setRemoteDescription(new RTCSessionDescription(answer));
    #   }
    #   call();
    # </script>

    # Make sure to install: pip install aiohttp aiortc
    asyncio.run(main())
