import aiohttp
import logging
import random
import asyncio
import json
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class SmappeeApiClient:
    def __init__(self, oauth_client, serial):
        _LOGGER.info("SmappeeApiClient init...")
        self.oauth_client = oauth_client
        self.base_url = "https://app1pub.smappee.net/dev/v3"
        self.serial = serial
        self._callbacks = set()
        self._loop = asyncio.get_event_loop()
        self._latestSessionCounter = 0
        self._sessionstate = "Initialize"
        self._timer = datetime.now() - timedelta(seconds = 10)
        _LOGGER.info("SmappeeApiClient init...done")

    @property
    def serial_id(self) -> str:
        return self.serial

    def enable(self) -> None:
        self._latestSessionCounter = random.randint(1, 10)   
        _LOGGER.info("SmappeeApiClient enable...")
        #self.publish_updates()
        self._loop.create_task(self.delayed_update())
        _LOGGER.info("SmappeeApiClient enable...done")
    
    async def delayed_update(self) -> None:
        _LOGGER.info("SmappeeApiClient delayed_update...")
        await self.oauth_client.ensure_token_valid()

        # Get the current time
        now = datetime.now()
        startsession = int(datetime(now.year-1, 6, 1).timestamp())
#        _LOGGER.debug(int(midnight.timestamp()))

        url = f"{self.base_url}/chargingstations/{self.serial}/sessions?active=false&range={startsession}"
        headers = {
            "Authorization": f"Bearer {self.oauth_client.access_token}",
            "Content-Type": "application/json",
        }
        _LOGGER.debug(f"Sending request to {url}")
        
        try:
            async with aiohttp.ClientSession() as session:
                response = await session.get(url, headers=headers)
                if response.status != 200:
                    if response.status == 401:
                        raise Exception("Token expired")
                    error_message = await response.text()
                    _LOGGER.error(f"Failed to get charging sessions: {error_message}")
                    raise Exception(f"Failed to get charging sessions: {error_message}")
                #_LOGGER.debug(f"200 Response API: {json.dumps(await response.json(), indent=5)}")
                sessions = await response.json()
                _LOGGER.debug("Set status...")
                self._sessionstate = sessions[0]["status"]
                _LOGGER.debug(f"SessionState: JSON {sessions[0]["status"]} VAR {self._sessionstate}")
                self._latestSessionCounter = sessions[0]["startReading"]+sessions[0]["energy"]
        except Exception as e:
            _LOGGER.error(f"Exception occurred while getting latest session counter: {str(e)}")
            raise
        
        await self.publish_updates()
        _LOGGER.info("SmappeeApiClient delayed_update...done")

    # In a real implementation, this library would call it's call backs when it was
    # notified of any state changeds for the relevant device.
    async def publish_updates(self) -> None:
        for callback in self._callbacks:
            callback()
            
    async def check_and_refresh_token():
        await self.oauth_client.ensure_token_valid()
        return True

    async def check_action_status():
        if self._latestSessionCounter == 0:
            return True
        else:
            return False

    def register_callback(self, callback: callable) -> None:
        """Register callback, called when Roller changes state."""
        self._callbacks.add(callback)

    def remove_callback(self, callback: callable) -> None:
        """Remove previously registered callback."""
        self._callbacks.discard(callback)

    @property
    def fetchLatestSessionCounter(self) -> int:
        if self._timer + timedelta (seconds = 10) < datetime.now():
            self._timer = datetime.now()
            self._loop.create_task(self.delayed_update())
        return self._latestSessionCounter

    @property
    def getSessionState(self) -> str:
        if self._timer + timedelta (seconds = 10) < datetime.now():
            self._timer = datetime.now()
            self._loop.create_task(self.delayed_update())
        return self._sessionstate
   
    async def set_charging_mode(self, mode, limit):
        """Set the charging mode for the given serial number and connector."""
        # Ensure token is refreshed if needed
        await self.oauth_client.ensure_token_valid()

        url = f"{self.base_url}/chargingstations/{self.serial}/connectors/1/mode"
        headers = {
            "Authorization": f"Bearer {self.oauth_client.access_token}",
            "Content-Type": "application/json",
        }

        # Create the base payload with the mode
        if mode == "NORMAL_PERCENTAGE":
            payload = {"mode": "NORMAL"}
        else:
            payload = {"mode": mode}
        
        # Add the limit only if the mode is NORMAL
        if mode == "NORMAL_PERCENTAGE":
            payload["limit"] = {"unit": "PERCENTAGE", "value": limit}
        if mode == "NORMAL":
            payload["limit"] = {"unit": "AMPERE", "value": limit}
        _LOGGER.debug(f"Sending request to {url} with payload {payload}")

        # Make the API request to set the charging mode
        try:
            async with aiohttp.ClientSession() as session:
                response = await session.put(url, json=payload, headers=headers)
                if response.status != 200:
                    if response.status == 401:
                        raise Exception("Token expired")
                    
                    error_message = await response.text()
                    _LOGGER.error(f"Failed to set charging mode: {error_message}")
                    raise Exception(f"Error setting charging mode: {error_message}")
                _LOGGER.debug("Successfully set charging mode")
        except Exception as e:
            _LOGGER.error(f"Exception occurred while setting charging mode: {str(e)}")
            raise
