"""
Insurance Broker MCP Server
============================
Custom MCP server for insurance brokerage operations.
Supports: ASF (Romania) + BaFin (Germany) regulated brokers.

Tools prefix: broker_
Transport: stdio (local) → streamable-http (cloud deployment)

Run locally:
    python -m insurance_broker_mcp.server
"""
from fastmcp import FastMCP
from insurance_broker_mcp.tools.client_tools import register_client_tools
from insurance_broker_mcp.tools.policy_tools import register_policy_tools
from insurance_broker_mcp.tools.product_tools import register_product_tools
from insurance_broker_mcp.tools.offer_tools import register_offer_tools
from insurance_broker_mcp.tools.claims_tools import register_claims_tools
from insurance_broker_mcp.tools.compliance_tools import register_compliance_tools
from insurance_broker_mcp.tools.analytics_tools import register_analytics_tools
from insurance_broker_mcp.tools.calculator_tools import register_calculator_tools
from insurance_broker_mcp.tools.compliance_check_tools import register_compliance_check_tools
from insurance_broker_mcp.tools.drive_tools import register_drive_tools

mcp = FastMCP(
    "insurance_broker_mcp",
    instructions="""
    Insurance brokerage management system for ASF (Romania) and BaFin (Germany) regulated operations.

    All tools use the prefix broker_. Available tool groups:
    - broker_search_clients / broker_get_client / broker_create_client
    - broker_search_products / broker_compare_products
    - broker_create_offer / broker_list_offers
    - broker_get_renewals_due / broker_list_policies
    - broker_log_claim / broker_get_claim_status
    - broker_asf_summary / broker_bafin_summary / broker_check_rca_validity
    - broker_cross_sell — analyze portfolio gaps and suggest products
    - broker_calculate_premium — estimate RCA/CASCO premiums from risk factors
    - broker_compliance_check — verify client file completeness

    Data: client PII stays within this server. Never expose ID numbers or financial data in plain text.
    Currency: RON for Romanian products, EUR for German products.
    Language: respond in English by default, switch to German or Romanian on request.
    """
)

register_client_tools(mcp)
register_policy_tools(mcp)
register_product_tools(mcp)
register_offer_tools(mcp)
register_claims_tools(mcp)
register_compliance_tools(mcp)
register_analytics_tools(mcp)
register_calculator_tools(mcp)
register_compliance_check_tools(mcp)
register_drive_tools(mcp)

if __name__ == "__main__":
    mcp.run()
