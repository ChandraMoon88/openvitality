import pjsua2 as pj
import os
import threading
import time
import logging

# Assuming a config module handles environment variables
# from src.core.config_loader import load_config_from_env

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SipAccount(pj.Account):
    def __init__(self, endpoint, on_incoming_call_cb):
        pj.Account.__init__(self)
        self.endpoint = endpoint
        self.on_incoming_call_cb = on_incoming_call_cb
        self.current_call = None

    def onRegState(self, prm):
        info = self.getInfo()
        if prm.code == 200:
            logger.info("SIP registration successful for account: %s", info.uri)
        else:
            logger.error("SIP registration failed for account: %s, code: %d, reason: %s",
                         info.uri, prm.code, prm.reason)

    def onIncomingCall(self, prm):
        logger.info("Incoming call from: %s", prm.src_address)
        if self.current_call:
            # Reject new call if already in one
            call = pj.Call(self, prm.call_id)
            call.answer(486, "Busy Here")
            call.hangup()
            logger.warning("Rejected incoming call, already in a call.")
            return

        call = SipCall(self, prm.call_id)
        self.current_call = call
        call_prm = pj.CallOpParam(True) # True to send 200 OK after this notification
        call.answer(200, "OK") # Answer the call
        logger.info("Incoming call answered.")
        if self.on_incoming_call_cb:
            threading.Thread(target=self.on_incoming_call_cb, args=(call,)).start()

    def onCallState(self, prm):
        if self.current_call:
            ci = self.current_call.getInfo()
            if ci.state == pj.CallState.PJSIP_INV_STATE_DISCONNECTED:
                logger.info("Call with %s is disconnected", ci.remote_uri)
                self.current_call = None

class SipCall(pj.Call):
    def __init__(self, account, call_id=pj.PJSUA_INVALID_ID):
        pj.Call.__init__(self, account, call_id)
        self.player_id = pj.PJSUA_INVALID_ID
        self.recorder_id = pj.PJSUA_INVALID_ID
        self.audio_data_queue = []
        self.is_running = True

    def onCallState(self, prm):
        ci = self.getInfo()
        logger.info("Call with %s state changed to %s", ci.remote_uri, ci.state_text)

        if ci.state == pj.CallState.PJSIP_INV_STATE_DISCONNECTED:
            self.is_running = False
            # Clean up media
            if self.player_id != pj.PJSUA_INVALID_ID:
                pj.Lib.instance().playerDestroy(self.player_id)
                self.player_id = pj.PJSUA_INVALID_ID
            if self.recorder_id != pj.PJSUA_INVALID_ID:
                pj.Lib.instance().recorderDestroy(self.recorder_id)
                self.recorder_id = pj.PJSUA_INVALID_ID
            logger.info("Call disconnected, media ports destroyed.")

    def onCallTsxState(self, prm):
        logger.info("Call transaction state changed")

    def onCallMediaState(self, prm):
        ci = self.getInfo()
        for media_idx in range(len(ci.media)):
            mi = ci.media[media_idx]
            if mi.type == pj.MediaType.PJMEDIA_TYPE_AUDIO and \
                    (mi.status == pj.MediaStatus.PJMEDIA_MED_STATUS_ACTIVE or \
                     mi.status == pj.MediaStatus.PJMEDIA_MED_STATUS_CONNECTED):
                # Connect the call audio to the sound device
                call_media = self.getMedia(media_idx)
                if call_media:
                    aud_med = pj.AudioMedia.typecastFromMedia(call_media)
                    # Connect to a bridge for processing (not sound device directly)
                    # For now, we'll connect it to a placeholder for future processing
                    # In a real scenario, this would connect to a custom media port
                    # that buffers audio for STT and injects audio for TTS.
                    pj.Lib.instance().audDevManager().getCaptureDevMedia().startTransmit(aud_med)
                    aud_med.startTransmit(pj.Lib.instance().audDevManager().getPlaybackDevMedia())
                    logger.info("SIP media connected for audio stream.")

    def send_audio_to_stt(self, audio_chunk):
        # Placeholder for sending audio to STT engine
        logger.debug("Sending audio chunk to STT (size: %d bytes)", len(audio_chunk))
        # This audio_chunk would typically be processed by a STT manager
        # e.g., self.stt_manager.process_audio(audio_chunk)
        pass

    def receive_audio_from_tts(self, audio_data):
        # Placeholder for receiving audio from TTS and playing it
        logger.debug("Receiving audio from TTS (size: %d bytes)", len(audio_data))
        # In a real system, this would involve playing the audio data
        # through a custom media port connected to the SIP call.
        pass

    def onDtmfDigit(self, prm):
        logger.info("Received DTMF digit: %s", prm.digit)
        # Handle DTMF for IVR menus here
        pass

class SipTrunkHandler:
    def __init__(self, on_incoming_call_cb=None):
        self.lib = pj.Lib.instance()
        self.account = None
        self.ep_cfg = pj.EpConfig()
        self.ua_cfg = pj.UaConfig()
        self.media_cfg = pj.MediaConfig()

        self.on_incoming_call_cb = on_incoming_call_cb
        self.is_initialized = False

    def init_lib(self):
        try:
            self.lib.init(self.ep_cfg, self.ua_cfg, self.media_cfg)
            # Default audio media format to PCMU
            self.lib.audDevManager().setCodecPriority("PCMU/8000", pj.PJMEDIA_CODEC_PRIO_MAX)
            self.lib.start()
            self.is_initialized = True
            logger.info("PJSIP library initialized and started.")
        except pj.Error as e:
            logger.error("PJSIP initialization failed: %s", e)
            self.is_initialized = False
            raise

    def configure_account(self, sip_server_ip, sip_server_port,
                          sip_username, sip_password, sip_extension, sip_domain):
        if not self.is_initialized:
            self.init_lib()

        acc_cfg = pj.AccountConfig()
        acc_cfg.idUri = f"sip:{sip_extension}@{sip_domain}"
        acc_cfg.regUri = f"sip:{sip_server_ip}:{sip_server_port}"
        acc_cfg.credVector.append(pj.AuthCredInfo("digest", sip_domain, sip_username, 0, sip_password))
        acc_cfg.registerOnAdd = True
        acc_cfg.setPublicAddress = True
        acc_cfg.regTimeoutSec = 300 # Re-register every 5 minutes
        acc_cfg.regInstanceId = f"<{pj.Lib.instance().generateUuid()}>" # Unique instance ID

        # Set up keep-alive for NAT traversal
        acc_cfg.keepAliveIntervalSec = 30 # Send OPTIONS every 30 seconds
        acc_cfg.regContactParams = ";+sip.instance=\"<urn:uuid:{uuid}>\";transport=UDP".format(uuid=pj.Lib.instance().generateUuid())

        self.account = SipAccount(self.lib, self.on_incoming_call_cb)
        self.account.create(acc_cfg)
        logger.info("SIP account configured for URI: %s", acc_cfg.idUri)

    def make_call(self, dest_uri):
        if not self.account:
            logger.error("SIP account not configured. Cannot make call.")
            return None
        if self.account.current_call:
            logger.warning("Already in a call. Cannot make new call.")
            return None

        logger.info("Making call to: %s", dest_uri)
        call = SipCall(self.account)
        call_prm = pj.CallOpParam(True)
        try:
            self.account.current_call = call
            call.makeCall(dest_uri, call_prm)
            logger.info("Call initiated to %s", dest_uri)
            return call
        except pj.Error as e:
            logger.error("Failed to make call to %s: %s", dest_uri, e)
            self.account.current_call = None
            return None

    def hangup_call(self):
        if self.account and self.account.current_call:
            logger.info("Hanging up current call.")
            op_prm = pj.CallOpParam()
            self.account.current_call.hangup(op_prm)
            self.account.current_call = None
        else:
            logger.info("No active call to hang up.")

    def destroy_lib(self):
        if self.is_initialized:
            try:
                if self.account:
                    self.account.delete()
                    self.account = None
                    logger.info("SIP account deleted.")
                self.lib.destroy()
                self.lib = None
                self.is_initialized = False
                logger.info("PJSIP library destroyed.")
            except pj.Error as e:
                logger.error("PJSIP destruction failed: %s", e)
        else:
            logger.info("PJSIP library not initialized.")

    def get_current_call(self):
        return self.account.current_call if self.account else None

# Example usage (for testing, will be integrated into main.py)
if __name__ == "__main__":
    # In a real scenario, these would come from .env or a config system
    SIP_SERVER_IP = os.getenv("SIP_SERVER_IP", "127.0.0.1")
    SIP_SERVER_PORT = os.getenv("SIP_SERVER_PORT", "5060")
    SIP_USERNAME = os.getenv("SIP_USERNAME", "gemini_ai")
    SIP_PASSWORD = os.getenv("SIP_PASSWORD", "supersecret")
    SIP_EXTENSION = os.getenv("SIP_EXTENSION", "1001")
    SIP_DOMAIN = os.getenv("SIP_DOMAIN", "localhost")

    def handle_incoming_call(call):
        logger.info("Custom handler: Call %s is now active.", call.getInfo().call_id_string)
        # Here you would integrate STT/TTS
        # For demonstration, just keep the call alive for a few seconds
        try:
            while call.is_running and call.getInfo().state == pj.CallState.PJSIP_INV_STATE_CONFIRMED:
                time.sleep(1)
        except Exception as e:
            logger.error("Error in handle_incoming_call: %s", e)
        finally:
            logger.info("Custom handler: Call %s ended.", call.getInfo().call_id_string)


    handler = SipTrunkHandler(on_incoming_call_cb=handle_incoming_call)
    try:
        handler.init_lib()
        handler.configure_account(SIP_SERVER_IP, SIP_SERVER_PORT, SIP_USERNAME,
                                  SIP_PASSWORD, SIP_EXTENSION, SIP_DOMAIN)

        logger.info("SIP handler is running. Waiting for incoming calls or press Ctrl+C to exit.")
        # Keep the main thread alive to allow PJSIP to process events
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Shutting down SIP handler.")
    except Exception as e:
        logger.critical("Unhandled error in main SIP handler: %s", e)
    finally:
        handler.destroy_lib()
