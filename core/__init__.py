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

"""The ProxyChat core: protocol, transport, crypto and server.

This package belongs to ProxyChat. Because ProxyNull will be written in a
different language (Rust) and its protocol will diverge deliberately, there
is no question of sharing code; what the two products share are the written
references, THREAT_MODEL.en.md and VOICE_CHAT_PLAN.en.md.

Two rules hold for the core (THREAT_MODEL.en.md, principles 1 and 2):

1. No plaintext work is done here -- decryption lives at the client edge.
2. Nothing is written to disk. Everything that needs to persist lives in the
   application layer.

Conveniences specific to the application (remembering settings,
notifications) do not belong here.
"""
