""" Le Config Flow """
import logging
from homeassistant.config_entries import ConfigFlow
from homeassistant.data_entry_flow import FlowResult
import voluptuous as vol

from .const import DOMAIN, AUTH_API, API_URL
from .frisquetAPI import FrisquetGetInfo

_LOGGER = logging.getLogger(__name__)


class FrisquetConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1
    data: dict = {}

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        if user_input is None:
            _LOGGER.debug(
                "config_flow step user (1). 1er appel : pas de user_input -> "
                "on affiche le form user_form"
            )
            return self.async_show_form(step_id="user", data_schema=vol.Schema(
                {
                    vol.Required("email"): str,
                    vol.Required("password"): str
                }
            ))

        self.data.update(user_input)

        # Crée une instance de FrisquetGetInfo avec les bons arguments

        #Newood  : ajout de "self."
        self.frisquet_api = FrisquetGetInfo(self.hass, self.data)
        
        #Newood : 1ère Authentification + récupération site
        auth = await self.frisquet_api.api_auth(
            user_input["email"],
            user_input["password"],
        )

        #Newood : token, email, password pour la suite
        self.data["email"] = user_input["email"]
        self.data["password"] = user_input["password"]
        self.data["token"] = auth["token"]

        #Newood : Récupération des sites
        self.data["sites"] = [s["nom"] for s in auth["utilisateur"]["sites"]]

        #Newood : ID chaudière site 0
        self.data["identifiant_chaudiere"] = auth["utilisateur"]["sites"][0]["identifiant_chaudiere"]

        return await self.async_step_2()

    async def async_step_2(self, user_input: dict | None = None):
        if len(self.data["sites"]) > 1:
            if user_input is None:
                return self.async_show_form(step_id="2", data_schema=vol.Schema(
                    {
                        vol.Required("site", default=0): vol.In(self.data["sites"]),
                    }
                ))
            self.data.update(user_input)
            site = self.data["sites"].index(user_input["site"])
        else:
            site = 0

        self.datadict = []
        for i in range(len(self.data["sites"])):
            self.datadict.append("")

        # Crée une instance de FrisquetGetInfo avec les bons arguments
        # frisquet_api = FrisquetGetInfo(self.hass, self.data)

        # Appelle getTokenAndInfo sur l'instance de FrisquetGetInfo avec les bons arguments
        #Newood  : ajout de "self."
        self.data[site] = await self.frisquet_api.getTokenAndInfo(self,self.data, 0, site)

        _LOGGER.debug("Config_Flow data=%s", self.data)

        self.datadict[site] = self.data[site]
        self.datadict[site]["nomInstall"] = self.data["sites"][site]
        self.datadict[site]["SiteID"] = site
        self.datadict[site]["email"] = self.data["email"]
        self.datadict[site]["password"] = self.data["password"]
        self.datadict[site]["token"] = self.data["token"]
        self.datadict[site]["identifiant_chaudiere"] = self.data["identifiant_chaudiere"]

        #await self.async_set_unique_id(str(self.datadict[site]["zone1"]["identifiant_chaudiere"]))
        await self.async_set_unique_id(str(self.datadict[site]["zone1"]["identifiant_chaudiere"]))
        return self.async_create_entry(title=self.datadict[site]["nomInstall"], data=self.datadict[site])
