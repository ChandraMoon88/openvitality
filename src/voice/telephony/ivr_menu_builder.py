import logging
import json
from typing import Dict, Any, Optional, Callable

logger = logging.getLogger(__name__)

class IVRMenuBuilder:
    def __init__(self, menu_config: Dict[str, Any], default_timeout_seconds: int = 10):
        """
        Initializes the IVRMenuBuilder with a menu configuration.

        Args:
            menu_config (Dict[str, Any]): A dictionary defining the IVR menu structure.
                                          Each key is a menu ID, and its value is a dict
                                          containing 'prompt', 'options', and optionally 'action'.
                                          Options map DTMF digits to next menu IDs or actions.
            default_timeout_seconds (int): Default seconds to wait for user input.
        """
        self.menu_config = menu_config
        self.default_timeout_seconds = default_timeout_seconds
        self.current_menu_id: str = "main_menu" # Default starting menu
        logger.info("IVRMenuBuilder initialized with menu config.")

    def get_menu_prompt(self, menu_id: str = None) -> Optional[str]:
        """
        Returns the spoken prompt for a given menu ID.
        """
        menu_id = menu_id if menu_id else self.current_menu_id
        menu = self.menu_config.get(menu_id)
        if menu and "prompt" in menu:
            return menu["prompt"]
        logger.warning(f"Menu ID '{menu_id}' not found or missing 'prompt'.")
        return None

    def get_menu_options_text(self, menu_id: str = None) -> Optional[str]:
        """
        Returns a human-readable string of options for a given menu ID.
        """
        menu_id = menu_id if menu_id else self.current_menu_id
        menu = self.menu_config.get(menu_id)
        if menu and "options" in menu:
            options_text = []
            for digit, item in menu["options"].items():
                if isinstance(item, dict) and "description" in item:
                    options_text.append(f"Press {digit} for {item['description']}.")
                elif isinstance(item, str): # Direct menu transition
                     next_menu = self.menu_config.get(item)
                     if next_menu and "description" in next_menu:
                         options_text.append(f"Press {digit} for {next_menu['description']}.")
                     else:
                         options_text.append(f"Press {digit} for option '{item}'.")
            
            # Add general "stay on line" for AI assistant
            if "default" in menu: # Assuming 'default' means AI assistant
                 options_text.append("Or stay on the line for the AI assistant.")
            return " ".join(options_text)
        return None

    def get_full_prompt_for_tts(self, menu_id: str = None) -> Optional[str]:
        """
        Combines the prompt and options text for TTS.
        """
        prompt = self.get_menu_prompt(menu_id)
        options = self.get_menu_options_text(menu_id)
        if prompt and options:
            return f"{prompt} {options}"
        elif prompt:
            return prompt
        return None

    def get_sms_options_text(self, menu_id: str = None) -> Optional[str]:
        """
        Generates text suitable for an SMS with menu options.
        """
        menu_id = menu_id if menu_id else self.current_menu_id
        menu = self.menu_config.get(menu_id)
        if menu and "options" in menu:
            sms_options = []
            sms_options.append(f"{self.get_menu_prompt(menu_id).split('.')[0].strip()}.\n"); # First sentence of prompt
            for digit, item in menu["options"].items():
                if isinstance(item, dict) and "description" in item:
                    sms_options.append(f"Reply {digit} for {item['description']}.")
                elif isinstance(item, str):
                    next_menu = self.menu_config.get(item)
                    if next_menu and "description" in next_menu:
                        sms_options.append(f"Reply {digit} for {next_menu['description']}.")
                    else:
                        sms_options.append(f"Reply {digit} for option '{item}'.")
            return "\n".join(sms_options)
        return None

    def navigate_menu(self, digit: str, menu_id: str = None) -> Optional[Dict[str, Any]]:
        """
        Navigates the menu based on the DTMF digit pressed.
        Returns the action/next menu ID, or None if input is invalid.
        """
        menu_id = menu_id if menu_id else self.current_menu_id
        menu = self.menu_config.get(menu_id)
        if menu and "options" in menu:
            option = menu["options"].get(digit)
            if option:
                if isinstance(option, str): # Direct transition to another menu
                    self.current_menu_id = option
                    logger.info(f"Navigated to menu: {self.current_menu_id}")
                    return {"type": "menu_transition", "next_menu_id": option}
                elif isinstance(option, dict) and "action" in option: # Execute an action
                    logger.info(f"Executing action for menu '{menu_id}', option '{digit}': {option['action']}")
                    return {"type": "action", "action_id": option["action"], "params": option.get("params", {})}
            elif "default" in menu:
                logger.info(f"Invalid option '{digit}', defaulting to AI assistant.")
                return {"type": "action", "action_id": menu["default"], "params": {}}
        logger.warning(f"Invalid digit '{digit}' or no default for menu '{menu_id}'.")
        return None

    def handle_timeout(self, menu_id: str = None) -> Optional[Dict[str, Any]]:
        """
        Handles the case where no DTMF input is received within the timeout.
        Defaults to repeating the prompt or a default action.
        """
        menu_id = menu_id if menu_id else self.current_menu_id
        menu = self.menu_config.get(menu_id)
        if menu and "timeout_action" in menu:
            logger.info(f"Timeout for menu '{menu_id}', executing timeout action: {menu['timeout_action']}")
            return {"type": "action", "action_id": menu["timeout_action"], "params": menu.get("timeout_params", {})}
        elif menu and "default" in menu:
            logger.info(f"Timeout for menu '{menu_id}', defaulting to AI assistant.")
            return {"type": "action", "action_id": menu["default"], "params": {}}
        else:
            logger.info(f"Timeout for menu '{menu_id}', repeating prompt.")
            return {"type": "repeat_prompt"} # Signal to repeat the current menu prompt
        
    def reset_to_main_menu(self):
        self.current_menu_id = "main_menu"
        logger.info("IVR menu reset to main_menu.")

# Example Usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Define a sample IVR menu configuration
    sample_menu_config = {
        "main_menu": {
            "prompt": "Welcome to AI Hospital. How can I help you today?",
            "description": "Main Menu",
            "options": {
                "1": {"description": "medical emergency", "action": "handle_emergency"},
                "2": "appointment_menu", # Transition to another menu
                "3": {"description": "speak to a human doctor", "action": "transfer_to_human"},
                "0": {"description": "repeat this menu", "action": "repeat_menu"}
            },
            "default": "connect_to_ai",
            "timeout_action": "connect_to_ai"
        },
        "appointment_menu": {
            "prompt": "For appointments, press 1 to book a new appointment, or 2 to reschedule existing one. Press 9 to go back to the main menu.",
            "description": "Appointment Menu",
            "options": {
                "1": {"description": "book new appointment", "action": "book_appointment"},
                "2": {"description": "reschedule appointment", "action": "reschedule_appointment"},
                "9": "main_menu"
            },
            "default": "connect_to_ai"
        }
    }

    ivr_builder = IVRMenuBuilder(sample_menu_config)

    print("\n--- Initial Menu ---")
    print(f"Current Menu: {ivr_builder.current_menu_id}")
    print(f"Full Prompt for TTS: {ivr_builder.get_full_prompt_for_tts()}")
    print(f"SMS Options: \n{ivr_builder.get_sms_options_text()}")

    # Simulate user pressing '1' (medical emergency)
    print("\n--- User presses '1' ---")
    result = ivr_builder.navigate_menu("1")
    if result and result["type"] == "action":
        print(f"Action triggered: {result['action_id']}")

    # Simulate user pressing '2' (appointment menu)
    print("\n--- User presses '2' ---")
    result = ivr_builder.navigate_menu("2")
    if result and result["type"] == "menu_transition":
        print(f"Transitioned to menu: {result['next_menu_id']}")
        print(f"Full Prompt for TTS: {ivr_builder.get_full_prompt_for_tts()}")
    
    # Simulate user pressing '1' in appointment menu (book new appointment)
    print("\n--- User presses '1' in Appointment Menu ---")
    result = ivr_builder.navigate_menu("1")
    if result and result["type"] == "action":
        print(f"Action triggered: {result['action_id']}")

    # Simulate user pressing '9' in appointment menu (go back to main)
    print("\n--- User presses '9' in Appointment Menu ---")
    result = ivr_builder.navigate_menu("9")
    if result and result["type"] == "menu_transition":
        print(f"Transitioned to menu: {result['next_menu_id']}")
        print(f"Full Prompt for TTS: {ivr_builder.get_full_prompt_for_tts()}")

    # Simulate invalid input
    print("\n--- User presses '5' (invalid) ---")
    result = ivr_builder.navigate_menu("5")
    if result and result["type"] == "action":
        print(f"Invalid input, defaulting to action: {result['action_id']}")

    # Simulate timeout
    print("\n--- Timeout occurs ---")
    result = ivr_builder.handle_timeout()
    if result and result["type"] == "action":
        print(f"Timeout, executing action: {result['action_id']}")
