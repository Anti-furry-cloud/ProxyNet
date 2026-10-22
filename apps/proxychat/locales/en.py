# ProxyChat — kendi sunucunda, uçtan uca şifreli sohbet
# Copyright (C) 2026 Anti-furry-cloud
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""English — the reference catalogue. Every other language has exactly these keys."""

NAME = "English"

TEXTS = {
    # --- Window ---------------------------------------------------------
    "window.language": "Interface language",
    "tray.wrote": "{user} wrote",
    "tray.content_hidden": "New message. In an encrypted room the content is not shown in notifications.",

    # --- Connect page ---------------------------------------------------
    "connect.subtitle": "Chat with your friends on your own server. Over Hamachi or your local network.",
    "connect.hint": "Host mode starts a server on this computer. Join mode connects to a Hamachi IP.",
    "connect.privacy_title": "PRIVACY",
    "connect.keep_history": "Keep room history (Host mode)",
    "connect.keep_history_tooltip": (
        "The server keeps the last 100 messages of each room in memory; people\n"
        "who join the room later can see them. Never written to disk.\n"
        "Careful: while this is on, EVERYONE who joins the room receives these\n"
        "messages in encrypted form, even without the room password. If the\n"
        "password is weak, they can crack it offline. Off by default."
    ),
    "connect.logging": "Keep a diagnostic log",
    "connect.logging_tooltip": (
        "Writes server events to a file: room name, event type and time.\n"
        "Message content, usernames and IP addresses are NOT written.\n"
        "Off by default; turn it on only while investigating a problem.\n"
        "Turning it off also deletes existing log files."
    ),
    "connect.title": "Connect",
    "connect.username": "Username",
    "connect.host_placeholder": "Hamachi IP or server IP",
    "connect.listen_placeholder": "Choose the network to listen on",
    "connect.listen_tooltip": (
        "The server only accepts connections from the selected network.\n"
        "If you pick Hamachi, strangers on the same Wi-Fi cannot reach the server.\n"
        "If your friends connect over the local network, pick the local IP."
    ),
    "connect.listen_all": "All networks (0.0.0.0)",
    "connect.network_local": "Local network",
    "connect.network_other": "Other network",
    "connect.port": "Port",
    "connect.room": "Room name",
    "connect.password": "Room password — if entered, messages are encrypted",
    "connect.show_password": "Show",
    "connect.hide_password": "Hide",
    "connect.copy_password": "Copy",
    "connect.password_copied": "Copied",
    "connect.copy_password_tooltip": (
        "Copies the password to the clipboard without showing it.\n"
        "It is kept out of Windows clipboard history and removed from the clipboard after 30 seconds."
    ),
    "connect.generate_password": "Generate",
    "connect.generate_password_tooltip": (
        "Creates a strong password from random words.\n"
        "Share it in person or over Signal — never over Discord or other apps that keep your messages."
    ),
    "connect.password_generated": (
        "New password created. Everyone in the room must enter exactly this. Tell it in person, "
        "or send it over Signal with disappearing messages — not over Discord, Instagram, SMS or e-mail."
    ),
    "connect.remember_password": "Remember room password",
    "connect.remember_password_tooltip": (
        "The password is encrypted and stored tied to your Windows account. "
        "Another account or another computer cannot read it."
    ),
    "connect.password_hint": (
        "If a password is entered, messages are encrypted on this device; the server "
        "only sees encrypted text. Everyone in the room must enter the same password."
    ),
    "connect.button": "Connect",
    "connect.mode_join": "Join mode: enter the server's Hamachi IP address.",
    "connect.mode_host": (
        "Host mode: the server runs on this computer.\n"
        "Choose the network to listen on. If you pick Hamachi, strangers on the same "
        "Wi-Fi cannot reach the server."
    ),
    "connect.mode_demo": (
        "Demo mode: a local server starts and fake users join the room.\n"
        "Use it to try the interface without friends."
    ),
    "connect.error_host_required": "A Hamachi IP is required.",
    "connect.error_choose_network": "Choose the network to listen on.",
    "connect.error_invalid_port": "The port must be a number between 1 and 65535.",
    "connect.connecting": "Connecting...",
    "connect.connected": "Connected.",
    "connect.connection_lost": "The connection was lost.",
    "connect.reconnect_gave_up": "Could not reconnect after {attempts} attempts.",
    "connect.previous_attempt_pending": "The previous connection attempt has not finished.",

    # --- Chat page ------------------------------------------------------
    "chat.waiting": "Waiting for connection",
    "chat.channels": "CHANNELS",
    "chat.add_room": "Add room",
    "chat.leave": "Disconnect",
    "chat.status_waiting": "Connection status: waiting",
    "chat.message_placeholder": "Write a message...",
    "chat.send": "Send",
    "chat.unverified_one": "Unverified user: 1",
    "chat.unverified_many": "Unverified users: {count}",
    "chat.unverified_over": "Unverified users: >{limit}",
    "chat.unverified_hint": "Click to see the names. These people have not proved they know the room password; what they write cannot be read.",
    "chat.emoji": "Add emoji",
    "chat.users": "Users",
    "chat.user_unverified": "{user}  · unverified",
    "chat.user_unverified_hint": (
        "This person has not proved they know the room password yet. The "
        "handshake may still be running, or their password is different. The "
        "user list comes from the server; the proof comes from the key exchange."
    ),
    "chat.user_verified_hint": "Has proved they know the room password.",
    "chat.voice_title": "VOICE CHAT",
    "chat.voice_join": "Join voice",
    "chat.voice_leave": "Leave voice",
    "chat.voice_mute": "Mute microphone",
    "chat.voice_microphone": "Microphone",
    "chat.voice_speaker": "Speaker",
    "chat.voice_device_default": "System default",
    "chat.voice_devices": "Audio devices",
    "chat.voice_devices_tooltip": "Choose the microphone and speaker",
    "chat.voice_devices_summary": "Microphone: {microphone}\nSpeaker: {speaker}",
    "chat.voice_gate": "Noise gate",
    "chat.voice_gate_tooltip": "Silences the microphone while you are not speaking, so keystrokes and hiss do not go through.",
    "chat.voice_threshold_tooltip": "Set the threshold: the bar should pass it while you speak and stay below it in silence.",
    "chat.voice_threshold_hint": "Threshold {value}. The bar should pass it while you speak.",
    "chat.voice_threshold_off": "The noise gate is off: whatever the microphone picks up goes through.",
    "chat.voice_state_off": "Voice is off.",
    "chat.voice_state_joining": "Joining voice...",
    "chat.voice_state_on": "Voice is on.",
    "chat.voice_alone": "Voice is on. Nobody else is in voice in this room.",
    "chat.switching_room": "Switching to # {room}...",
    "chat.joined_self": "{user} joined the channel.",
    "chat.away_gap": "— Messages sent while you were not in this room did not reach you. —",
    "chat.user_joined": "{user} joined the channel.",
    "chat.user_left": "{user} left the channel.",
    "chat.user_moved": "{user} went to another room.",
    "chat.user_moved_many": "{user} went to another room (×{count}).",
    "chat.user_moved_back": "{user} went to another room and came back.",
    "chat.user_moved_back_many": "{user} went to another room and came back (×{count}).",
    "chat.user_returned": "{user} came back to the channel.",
    "chat.connected": "Connected",
    "chat.user_count_one": "{count} user connected",
    "chat.user_count": "{count} users connected",
    "chat.connected_to": "Connected: {host}:{port}",
    "chat.lock_encrypted": "🔒 End-to-end encrypted",
    "chat.lock_plain": "🔓 No room password",
    "chat.lock_encrypted_tooltip": (
        "Messages are encrypted on this device; nobody can read them,\n"
        "including the person running the server."
    ),
    "chat.lock_plain_tooltip": (
        "Messages are not encrypted because no room password was entered.\n"
        "To encrypt them, enter a room password when connecting and share\n"
        "the same password with everyone in the room."
    ),
    "chat.encrypted_notice": (
        "Room password entered: messages are encrypted on this device, "
        "the server cannot see their content."
    ),
    "chat.plain_notice": (
        "No room password entered: messages are not encrypted. To encrypt them, "
        "enter a room password when connecting and share the same password with "
        "your friends."
    ),
    "chat.share_addresses": "Addresses your friends can connect to:",
    "chat.share_address": "Address your friends connect to:",
    "chat.reveal_address": "Show address",
    "chat.reveal_address_tooltip": "The address is hidden so it doesn't leak on a stream or a recording. Hold to see it; it hides again when you let go.",
    "chat.copy_addresses": "Copy address",
    "chat.address_copied": "Copied",
    "chat.ready": "Connection ready.",
    "chat.closed": "Connection closed",
    "chat.reconnecting_status": "Connection lost — retrying ({attempt}/{total})",
    "chat.reconnecting_notice": "Connection lost. Reconnecting... ({attempt}/{total})",
    "chat.reconnected": "Connection re-established.",
    "chat.message_too_long": "The message is too long to send. Shorten it or split it into several messages.",
    "chat.undecryptable": "[could not decrypt — different room password]",
    "chat.undecryptable_version": "[could not decrypt — the other side uses a different ProxyChat version]",
    "chat.undecryptable_sender": "[not shown — the sender could not be verified for this name]",
    # Messages from earlier days: "{day} {month} {time}", e.g. "9 Sep 14:05".
    "chat.date_format": "{day} {month} {time}",
    "chat.months": "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec",

    # --- Demo users -----------------------------------------------------
    "demo.message_1": "Hi, this is the demo room.",
    "demo.message_2": "The message list and the user list are being tested here.",
    "demo.message_3": "Switching rooms and multiple clients work.",

    # --- Errors ---------------------------------------------------------
    "error.generic": "Error",
    "error.voice_device": "The audio device does not support 16 kHz mono capture; voice chat could not start.",
    "error.voice_device_switch": "The selected audio device could not be opened; the call continues on the previous one.",
    "error.voice_not_connected": "Join a room first to use voice chat.",
    "error.voice_no_server": "The server did not answer the voice request; it may be an older version. Both sides need the same version.",
    "error.voice_codec": "Voice in this room uses a codec this computer does not have (Opus). You could not join; everyone needs the same installation.",
    "error.connection": "Connection error",
    "socket_error.10013": "Another program is already using this port (10013). Choose another port or close that program.",
    "socket_error.10048": "This port is already in use (10048). Choose another port or stop the other server.",
    "socket_error.10049": "The selected address is not available on this computer (10049). Is Hamachi still connected?",
    "socket_error.10053": "Connection aborted (10053). The other side closed the session or the link dropped.",
    "socket_error.10060": "Connection timed out (10060). Check the host IP, the port, and firewall or VPN rules.",
    "socket_error.10061": "The target refused the connection (10061). The server may not be running yet.",
    "socket_error.other": "{name}: {detail}",

    # Error packets from the server carry a "code"; see core/server.py.
    "server_error.server_full": "The server is full.",
    "server_error.join_timeout": "The join request did not arrive in time.",
    "server_error.join_required": "The server expected a join request first.",
    "server_error.idle_timeout": "The connection was idle for too long.",
    "server_error.malformed_packet": "The server received a malformed packet.",
    "server_error.malformed_packet_ignored": "A malformed packet was ignored.",
    "server_error.packet_too_large": "A packet exceeded the size limit.",
    "server_error.message_too_long": "The message is too long.",
    "server_error.rate_limited": "You are sending messages too fast, wait a moment.",
}

# Passphrase words: lowercase ASCII, 3-8 letters, concrete and easy to say
# aloud. Order does not matter; duplicates are rejected by the tests.
WORDS = tuple("""
apple apron arch arena arm arrow art ash atlas attic autumn axe
bacon badge bag baker ball bamboo banana band bank barn basket bat bath beach
bead beam bean bear beard bed bee beef bell belt bench berry bike bird blade
blanket bloom board boat bolt bone book boot bottle bowl box brain branch brass
bread brick bridge broom brush bubble bucket bud buffalo bulb bull bunny bus
bush butter button cabin cable cactus cake camel camera camp candle candy canoe
canvas cap captain car card cargo carpet carrot cart castle cat cave cedar chain
chair chalk cheese cherry chess chest chicken chimney chip circle city clam claw
clay cliff clock cloud clover coach coal coast coat cobra cocoa coconut coffee
coin comet cookie copper coral cord corn cotton couch cow crab crane crayon
cream creek crow crown cube cup curtain cushion daisy dance deer desert desk
diamond dice dinner dish dog doll dolphin donkey door dove dragon drawer dream
dress drill drum duck dune dust eagle ear earth easel echo egg elbow elephant
elk ember engine eraser falcon fan farm feather fence fern ferry field fig
finger fire fish flag flame flask flute foam fog fork fossil fox frame frog
frost fruit garden garlic gate gecko gem giant ginger glass glove goat gold
goose grape grass gravel guitar gull hammer hand harbor harp hat hawk hazel
heart hedge helmet hen herb hill hive honey hook horn horse hotel house igloo
ink iron island ivory ivy jacket jam jar jeans jelly jewel juice kettle key kite
kitten kiwi knee knot koala ladder ladle lake lamb lamp lantern laser lava lawn
leaf lemon lens letter lettuce lily lime lion lizard llama lobster lock log
lotus magnet mango map maple marble market mask meadow melon metal meteor milk
mint mirror mitten mole monkey moon moose moss moth motor mouse mud mug mule
muffin museum music nail needle nest net night noodle nose notebook nut oak oar
ocean olive onion orange orbit otter oven owl paddle page paint palace palm pan
panda paper parrot pasta path peach peanut pear pebble pencil penguin pepper
piano pickle pie pig pillow pine pipe pizza planet plant plate plum pocket poem
pond pony popcorn potato pot pumpkin puppy puzzle quartz quilt rabbit radar
radio raft rain rainbow raven reef ribbon rice ring river road robin robot rock
rocket roof root rope rose ruby rug ruler saddle sail salad salmon salt sand
satchel scarf school seal seed shadow shark sheep shelf shell ship shirt shoe
shovel silk silver sink skate ski sky sled slope snail snake snow soap sock sofa
soup spade spark spider spoon spring squid stable stair star steam steel stem
stone stool storm stove straw stream street sugar suit summer sun swan sweater
swing table tablet taco tail tank tea teapot tent thorn thread throne thumb
tiger tile timber toast toe tomato tooth torch tower town toy tractor train tree
truck trumpet tulip tunnel turtle twig umbrella unicorn valley vase velvet
violin volcano wagon wall walnut walrus wand wave wax whale wheat wheel whistle
willow wind window wing winter wire wolf wood wool worm yacht yarn yogurt zebra
zipper
""".split())
