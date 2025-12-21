import logging
import aiohttp
import random
import string
import datetime
import copy
from .const import AUTH_API, API_URL

_LOGGER = logging.getLogger(__name__)


class FrisquetGetInfo:
    def __init__(self, hass, entry_data):
        self.hass = hass
        self.data: dict = {}
        self.previousdata = {}
        self.entry_data = entry_data  # Stocke les données de configuration

    def generer_Appid_random(self, longueur=22):
        caracteres = string.ascii_letters + string.digits
        return ''.join(random.choice(caracteres) for _ in range(longueur))

    async def api_auth(self,email, password):
        payload = {
            "locale": "fr",
            "email": email,
            "password": password,
            "type_client": "IOS",
        }

        _LOGGER.debug("Authentification payload : %s",payload)

        headers = {
            'Accept-Language': 'FR',
            'Android-Version': '2.8.1',
            'Content-Type': 'application/json; charset=UTF-8',
            'Connection': 'Keep-Alive',
            'Accept-Encoding': 'gzip',
            'User-Agent': 'okhttp/4.12.0'
        }
            #'Content-Length': str(len(str(payload))),
            #'Host': 'fcutappli.frisquet.com',
        appid = self.generer_Appid_random()
        _AUTH_API = AUTH_API + '?app_id=' + appid
        _LOGGER.debug("Authentification call : %s",_AUTH_API)

        #_session = aiohttp.ClientSession(headers="")

        async with aiohttp.ClientSession() as session:
            async with session.post(url=_AUTH_API, headers=headers, json=payload) as resp:
                if resp.status != 201:
                    raise Exception(f"Authentification failed with http ({resp.status})")
                return await resp.json()

    async def getTokenAndInfo(self, entry, data, idx, site, retry=False):
        #retry=False : Pour pouvoir relancé 1 fois ne cas de token expiré
        _LOGGER.debug("JKS entry data : %s",entry.data  )
        # Credentials
        #email    = entry.data["zone1"]["email"]
        #password = entry.data["zone1"]["password"]
        # Si on a une zone sinon prendre l'entrée du formulaire
        #if entry.data.get("zone1"):
        #    email = zone1["email"]
        #    password = zone1["password"]
       # else:
        email = entry.data.get("email")
        password = entry.data.get("password")
        # Authentification 
        token = data.get("token")
        auth_json_reply = None

        if not token:
            auth_json_reply = await self.api_auth(email, password)
            token = auth_json_reply.get("token")
            if not token:
                raise Exception("Frisquet API did not return a token")
            data["token"] = token

            # Récupération des sites 
            data["sites"] = []
            for i in range(len(auth_json_reply["utilisateur"]["sites"])):
                data["sites"].append(auth_json_reply["utilisateur"]["sites"][i]["nom"])

        # ID Chaufière 

        if auth_json_reply:
            identifiant = auth_json_reply["utilisateur"]["sites"][site]["identifiant_chaudiere"]
        else:
            identifiant = data["identifiant_chaudiere"]

        
        # GET API - Config  
        headers = {"User-Agent": "okhttp/4.12.0"}
        url = API_URL + identifiant + "?token=" + token

        _LOGGER.debug(" GET API : %s", url) 

        # GET API - Call  
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as resp:
                # Si token expiré
                if resp.status in (401, 403):
                    if retry:
                        _LOGGER.error("Token invalid after re-login, aborting")
                        return self.previousdata
                    data.pop("token", None)
                    return await self.getTokenAndInfo(entry, data, idx, site, retry=True)
                
                response = await resp.json()

        #Anonimized
        reponseAnonimized = response
        reponseAnonimized["code_postal"] = ""
        reponseAnonimized["emails_alerte"] = ""

        _LOGGER.debug("In getToken and info Frisquet API, response : %s", reponseAnonimized)

        site_name = data.get("nomInstall", f"site_{site}")

        if "zones" in response or idx == 0:
            for i in range(len(response["zones"])):
                if response["zones"][i]["numero"] != "":
                    if i == 0:
                        self.data[site_name] = {}
                        self.data[site_name]["alarmes"] = {}

                    self.data[site_name]["alarmes"]                                   = response["alarmes"]
                    self.data[site_name]["zone"+  str(i+1)]                           = {}
                    self.data[site_name]["zone" + str(i+1)]                           = response["zones"][i]["carac_zone"]
                    self.data[site_name]["zone" + str(i+1)]["boost_disponible"]       = response["zones"][i]["boost_disponible"]
                    self.data[site_name]["zone" + str(i+1)]["identifiant"]            = response["zones"][i]["identifiant"]
                    self.data[site_name]["zone" + str(i+1)]["numero"]                 = response["zones"][i]["numero"]
                    self.data[site_name]["zone" + str(i+1)]["nom"]                    = response["zones"][i]["nom"]
                    self.data[site_name]["zone" + str(i+1)]["programmation"]          = response["zones"][i]["programmation"]
                    self.data[site_name]["zone" + str(i+1)]["date_derniere_remontee"] = response["date_derniere_remontee"]

                    if response["produit"]["chaudiere"] == None:
                        self.data[site_name]["zone" + str(i+1)]["produit"]    = "Not defined"
                    else:
                        self.data[site_name]["zone" + str(i+1)]["produit"]    = response["produit"]["chaudiere"]+" "+response["produit"]["gamme"]+" " + response["produit"]["puissance"]

                    self.data[site_name]["zone" + str(i+1)]["identifiant_chaudiere"]    = response["identifiant_chaudiere"]

                    self.data[site_name]["zone" + str(i+1)]["token"] = token
                    
                    if "sites" in data:
                        self.data[site_name]["nomInstall"]    = data["sites"][site]
                        self.data[site_name]["siteID"]        = site
                        self.data["nomInstall"]                         = data["sites"][site]
                    elif "nomInstall" in data:
                        self.data[site_name]["nomInstall"]    = data["nomInstall"]
                        self.data[site_name]["siteID"]        = site
                        self.data["nomInstall"]                         = data["nomInstall"]

                    self.data[site_name]["zone" + str(i+1)]["email"]          = email
                    self.data[site_name]["zone" + str(i+1)]["password"]       = password
                    self.data[site_name]["zone" + str(i+1)]["T_EXT"]          = response["environnement"]["T_EXT"]

                    self.data[site_name]["modes_ecs_"]        = {}

                    for w in range(len(response["modes_ecs"])):
                        nomModeECS: str
                        idModeECS: str
                        nomModeECS = response["modes_ecs"][w]["nom"]
                        nomModeECS = nomModeECS.replace("\ue809", "Timer")
                        idModeECS = response["modes_ecs"][w]["id"]
                        self.data[site_name]["modes_ecs_"][nomModeECS] = {}
                        self.data[site_name]["modes_ecs_"][nomModeECS] = idModeECS


            self.data[site_name]["ecs"] = response["ecs"]

            self.data["email"]                  = email
            self.data["password"]               = password
            self.data["identifiant_chaudiere"]  = identifiant
            
            #Conso
            try:
                url2 = (API_URL + identifiant +"/conso?token=" + token +"&types[]=CHF&types[]=SAN")

                async with aiohttp.ClientSession(headers=headers) as session2:
                    async with session2.get(url2) as resp2:
                        conso = await resp2.json()

                self.data[site_name]["zone1"]["energy"] = {}
                self.data[site_name]["zone1"]["energy"]["CHF"] = sum(
                    c["valeur"] for c in conso.get("CHF", [])
                )

                if "SAN" in conso:
                    self.data[site_name]["zone1"]["energy"]["SAN"] = sum(
                        c["valeur"] for c in conso.get("SAN", [])
                )

            except Exception:
                _LOGGER.debug("Conso unavailable")

            #Save
            self.previousdata = copy.deepcopy(self.data)


            if idx == 0:
                return self.data[site_name]
            else:
                return self.data[site_name][idx]


        return self.previousdata
