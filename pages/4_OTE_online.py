"""
pages/4_OTE_online.py – dočasný debug: výpis metod ČEPS SOAP API
"""

import streamlit as st
import requests
from zeep import Client
from zeep.transports import Transport
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from navigation import show_nav

st.set_page_config(page_title="OTE online – debug", page_icon="🔌", layout="wide")

WSDL = "https://vip-prod-service-00-azapp.azurewebsites.net/_layouts/cepsdata.asmx?WSDL"

st.title("ČEPS SOAP – dostupné metody")

try:
    session = requests.Session()
    client = Client(WSDL, transport=Transport(session=session))

    methods = []
    for service in client.wsdl.services.values():
        for port in service.ports.values():
            for op_name in port.binding._operations.keys():
                methods.append(op_name)

    st.success(f"Nalezeno {len(methods)} metod:")
    for m in sorted(methods):
        st.code(m)

except Exception as e:
    st.error(f"Chyba: {e}")
