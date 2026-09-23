"""Investable theme baskets for the theme tape.

Each basket is an equal-weight list of US-listed common stocks or major ADRs.
ETFs are labels only and are not mixed into the average.
"""

from __future__ import annotations


LANE_ORDER = ["Semis", "AI", "Health", "Power", "Materials", "Macro"]


def theme(theme_id: str, name: str, lane: str, blurb: str, tickers: list[str], etf: str | None = None) -> dict:
    return {
        "id": theme_id,
        "name": name,
        "lane": lane,
        "blurb": blurb,
        "tickers": tickers,
        "etf": etf,
    }


THEMES: list[dict] = [
    theme(
        "gpus",
        "GPUs",
        "Semis",
        "Merchant GPUs and the custom AI accelerators that sit next to them.",
        ["NVDA", "AMD", "AVGO", "MRVL", "ARM", "ALAB", "CRDO", "AMBA"],
        "SMH",
    ),
    theme(
        "cpus",
        "CPUs",
        "Semis",
        "Server, PC, and custom CPU franchises. NVIDIA stays in GPUs.",
        ["INTC", "AMD", "ARM", "QCOM", "AVGO", "IBM"],
    ),
    theme(
        "memory",
        "Memory",
        "Semis",
        "DRAM, NAND, and HBM suppliers plus the US memory-controller names.",
        ["MU", "WDC", "SNDK", "STX", "SIMO", "RMBS"],
    ),
    theme(
        "hbm",
        "HBM",
        "Semis",
        "Micron is the US HBM supplier. Packaging and probe names are what the tape trades with the stacks.",
        ["MU", "AMKR", "ASX", "FORM", "CAMT", "NVMI"],
        "DRAM",
    ),
    theme(
        "nand",
        "NAND",
        "Semis",
        "Sandisk after the Western Digital spin, plus Micron and the NAND controller name.",
        ["SNDK", "MU", "SIMO"],
        "DRAM",
    ),
    theme(
        "mlcc",
        "MLCC",
        "Semis",
        "US-listed capacitor and passive exposure. Merchant MLCC volume is mostly Japan, Korea, and Taiwan.",
        ["VSH", "KN", "BELFB", "CTS", "VPG", "LFUS"],
    ),
    theme(
        "semi_testing",
        "Semi Testing",
        "Semis",
        "Automated test, probe, and process-control tools.",
        ["TER", "KLAC", "ONTO", "COHU", "FORM", "AEHR", "CAMT", "NVMI"],
    ),
    theme(
        "semi_equipment",
        "Semi Equipment",
        "Semis",
        "Wafer-fab equipment: deposition, etch, lithography, and process control.",
        ["AMAT", "LRCX", "ASML", "KLAC", "TER", "ONTO", "MKSI", "ACLS", "CAMT", "VECO", "NVMI"],
        "SMH",
    ),
    theme(
        "foundry",
        "Foundry",
        "Semis",
        "Contract wafer makers and the US foundry effort.",
        ["TSM", "GFS", "UMC", "INTC", "ASX", "TSEM"],
    ),
    theme(
        "advanced_packaging",
        "Advanced Packaging",
        "Semis",
        "OSAT and the tools aimed at advanced packaging.",
        ["AMKR", "ASX", "TSEM", "ONTO", "CAMT", "FORM", "KLIC"],
    ),
    theme(
        "analog",
        "Analog Semis",
        "Semis",
        "Analog, mixed-signal, and broad-catalog chip suppliers.",
        ["TXN", "ADI", "MCHP", "NXPI", "ON", "MPWR", "ALGM", "DIOD", "POWI", "MTSI", "SMTC", "SLAB"],
    ),
    theme(
        "power_semis",
        "Power Semis",
        "Semis",
        "Power management and wide-bandgap chip suppliers.",
        ["ON", "MPWR", "NVTS", "ALGM", "STM", "TXN", "DIOD", "POWI", "WOLF", "AOSL"],
    ),
    theme(
        "rf_semis",
        "RF Semis",
        "Semis",
        "RF front-end and wireless chipmakers. Skyworks and Qorvo still trade on their own.",
        ["QCOM", "SWKS", "QRVO", "MTSI", "NXPI", "STM"],
    ),
    theme(
        "optical",
        "Optical",
        "Semis",
        "Silicon photonics, optical components, and high-speed interconnect.",
        ["COHR", "LITE", "AAOI", "CIEN", "FN", "CRDO", "ALAB", "MTSI", "VIAV", "NOVT"],
    ),
    theme(
        "eda",
        "EDA Software",
        "Semis",
        "Chip-design software and the IP that ships with it.",
        ["SNPS", "CDNS", "ARM", "KEYS", "PDFS"],
    ),
    theme(
        "pcb",
        "PCB and EMS",
        "Semis",
        "Boards, substrates, and the contract manufacturers that build them.",
        ["TTMI", "FLEX", "CLS", "SANM", "JBL", "PLXS", "ROG"],
    ),
    theme(
        "connectors",
        "Connectors",
        "Semis",
        "Connectors, fiber, and interconnect hardware.",
        ["APH", "TEL", "FN", "GLW", "BDC", "LFUS", "ITT"],
    ),
    theme(
        "semi_materials",
        "Semi Materials",
        "Semis",
        "Specialty materials and subsystems sold into the fab.",
        ["ENTG", "MKSI", "ASYS", "UCTT", "PLAB", "AXTI", "ICHR"],
    ),
    theme(
        "robotics",
        "Robotics",
        "AI",
        "Robot makers and the automation stacks sold into factories and hospitals.",
        ["ISRG", "SYM", "ROK", "CGNX", "TER", "PATH", "ZBRA", "SERV"],
        "BOTZ",
    ),
    theme(
        "industrial_automation",
        "Industrial Automation",
        "AI",
        "Factory controls, motion, and the equipment installed on the line.",
        ["ROK", "EMR", "HON", "ETN", "CGNX", "ZBRA", "IR", "PH", "ITW"],
        "ROBO",
    ),
    theme(
        "humanoid",
        "Humanoid Robots",
        "AI",
        "Companies with a marketed humanoid or mobile-robot platform. The listed set is still thin.",
        ["TSLA", "SERV", "SYM", "RR", "PATH", "CGNX"],
    ),
    theme(
        "agentic_ai",
        "Agentic AI",
        "AI",
        "Software platforms selling agents and AI applications, not the chips underneath.",
        ["PLTR", "PATH", "NOW", "CRM", "SNOW", "DDOG", "MDB", "GTLB", "AI", "SOUN", "BBAI", "ESTC"],
    ),
    theme(
        "edge_ai",
        "Edge AI",
        "AI",
        "Inference at the device: handset, camera, FPGA, and edge SoCs.",
        ["QCOM", "ARM", "AMBA", "LSCC", "SYNA", "CRUS", "NXPI", "STM", "INTC", "POWI"],
    ),
    theme(
        "routers",
        "Routers",
        "AI",
        "Routing, switching, and optical transport. Juniper sits inside HPE.",
        ["CSCO", "ANET", "HPE", "NOK", "ERIC", "CIEN", "FFIV", "EXTR", "CALX", "VIAV"],
    ),
    theme(
        "neoclouds",
        "Neoclouds",
        "AI",
        "GPU clouds and the miners that pivoted capacity to AI compute.",
        ["CRWV", "NBIS", "IREN", "CORZ", "WULF", "APLD", "HUT", "CIFR", "GDS"],
    ),
    theme(
        "hyperscalers",
        "Hyperscalers",
        "AI",
        "The platforms that buy the GPUs and rent the compute.",
        ["MSFT", "AMZN", "GOOGL", "META", "ORCL", "IBM"],
    ),
    theme(
        "dc_reits",
        "Data Center REITs",
        "AI",
        "Landlords of the server halls.",
        ["DLR", "EQIX", "IRM"],
    ),
    theme(
        "dc_power",
        "Data Center Power",
        "AI",
        "Power, cooling, and electrical gear aimed at data-center buildout.",
        ["VRT", "ETN", "GEV", "PWR", "HUBB", "FIX", "EME", "POWL", "MOD", "TT"],
    ),
    theme(
        "cyber",
        "Cybersecurity",
        "AI",
        "Network, cloud, and identity security platforms.",
        ["CRWD", "PANW", "ZS", "FTNT", "NET", "S", "OKTA", "TENB", "QLYS", "CHKP", "RPD", "GEN"],
        "HACK",
    ),
    theme(
        "ai_servers",
        "AI Servers",
        "AI",
        "Server OEMs and the manufacturers assembling AI racks.",
        ["SMCI", "DELL", "HPE", "CLS", "FN", "JBL", "HPQ"],
    ),
    theme(
        "autonomy",
        "Autonomous Driving",
        "AI",
        "Vehicle autonomy programs and the sensor suppliers tied to them.",
        ["TSLA", "GOOGL", "GM", "MBLY", "APTV", "AUR"],
    ),
    theme(
        "drones",
        "Drones",
        "AI",
        "Unmanned aircraft makers and the primes with drone franchises.",
        ["AVAV", "KTOS", "RC", "EH", "LMT", "NOC", "RTX", "AXON"],
    ),
    theme(
        "quantum",
        "Quantum Computing",
        "AI",
        "Listed quantum-computing developers. Revenue is still small versus the narrative.",
        ["IONQ", "RGTI", "QBTS", "QUBT", "IBM", "HON", "GOOGL", "MSFT"],
    ),
    theme(
        "glp1",
        "GLP-1",
        "Health",
        "Incretin drugs on the market and the next-wave obesity programs.",
        ["LLY", "NVO", "AMGN", "VKTX", "GPCR", "ALT", "PFE", "NVS", "REGN"],
    ),
    theme(
        "devices",
        "Medical Devices",
        "Health",
        "Large-cap devices, surgical robotics, and diabetes hardware.",
        ["ISRG", "SYK", "BSX", "MDT", "EW", "ABT", "ZBH", "DXCM", "PODD", "INSP", "RMD", "COO"],
    ),
    theme(
        "radiopharma",
        "Radiopharma",
        "Health",
        "Radiopharmaceutical diagnostics and the pharma owners of the therapy programs.",
        ["LNTH", "LLY", "NVS", "AZN", "TLX", "GEHC"],
    ),
    theme(
        "nuclear",
        "Nuclear Power",
        "Power",
        "Utilities and merchants whose earnings are tied to nuclear fleets.",
        ["CEG", "VST", "TLN", "NRG", "EXC", "DUK", "SO", "PEG", "ETR", "BWXT"],
    ),
    theme(
        "ipps",
        "Independent Power",
        "Power",
        "Merchants and IPPs leveraged to wholesale power and data-center load.",
        ["VST", "NRG", "TLN", "AES", "CEG", "CWEN"],
    ),
    theme(
        "advanced_nuclear",
        "Advanced Nuclear",
        "Power",
        "Small-modular and advanced-reactor developers. Separate from the operating fleet.",
        ["OKLO", "SMR", "NNE", "LEU"],
    ),
    theme(
        "uranium",
        "Uranium",
        "Power",
        "Uranium miners and the fuel-cycle names.",
        ["CCJ", "UEC", "UUUU", "DNN", "NXE", "LEU", "URG", "EU"],
        "URA",
    ),
    theme(
        "grid",
        "Grid Equipment",
        "Power",
        "Transmission, substations, and the contractors building the grid.",
        ["ETN", "HUBB", "PWR", "GEV", "VRT", "EME", "FIX", "MYRG", "POWL", "NVT"],
    ),
    theme(
        "lng",
        "LNG",
        "Power",
        "LNG exporters and the gas pipes that feed them.",
        ["LNG", "WMB", "KMI", "EPD", "ET", "TRGP", "OKE", "SHEL", "TTE", "EQNR"],
    ),
    theme(
        "solar",
        "Solar",
        "Power",
        "Module makers, inverters, and utility-scale solar developers.",
        ["FSLR", "ENPH", "SEDG", "ARRY", "NXT", "RUN", "CSIQ", "JKS", "DQ", "SHLS"],
        "TAN",
    ),
    theme(
        "batteries",
        "Batteries",
        "Materials",
        "Battery materials and listed cell or storage developers.",
        ["ALB", "QS", "ENVX", "AMPX", "TSLA", "ENS", "FLNC", "STEM"],
        "LIT",
    ),
    theme(
        "copper",
        "Copper",
        "Materials",
        "Copper miners leveraged to grid and data-center demand.",
        ["FCX", "SCCO", "TECK", "HBM", "BHP", "RIO", "ERO", "VALE"],
        "COPX",
    ),
    theme(
        "rare_earths",
        "Rare Earths",
        "Materials",
        "US-listed rare-earth miners. The set outside MP is thin.",
        ["MP", "UUUU", "USAR", "CRML", "METC"],
        "REMX",
    ),
    theme(
        "lithium",
        "Lithium",
        "Materials",
        "Lithium producers and developers.",
        ["ALB", "SQM", "LAC", "SGML", "LAR", "ELVR"],
        "LIT",
    ),
    theme(
        "gold",
        "Gold Miners",
        "Materials",
        "Senior gold producers and the royalty companies.",
        ["NEM", "AEM", "B", "KGC", "AU", "GFI", "WPM", "FNV", "RGLD", "HMY"],
        "GDX",
    ),
    theme(
        "silver",
        "Silver Miners",
        "Materials",
        "Primary silver miners and a royalty name with silver exposure.",
        ["PAAS", "AG", "HL", "CDE", "EXK", "FSM", "WPM", "BVN"],
        "SIL",
    ),
    theme(
        "defense",
        "Defense",
        "Macro",
        "Primes, subsystems, and the smaller unmanned franchises.",
        ["LMT", "RTX", "NOC", "GD", "HII", "LHX", "LDOS", "BA", "HWM", "TDG", "KTOS", "AVAV"],
        "ITA",
    ),
    theme(
        "space",
        "Space",
        "Macro",
        "Launch, lunar, and satellite operators, plus the primes that still own the budgets.",
        ["RKLB", "LUNR", "ASTS", "RDW", "PL", "IRDM", "SPCX", "FLY", "VSAT", "GSAT"],
        "UFO",
    ),
    theme(
        "crypto_miners",
        "Crypto Miners",
        "Macro",
        "Listed bitcoin miners.",
        ["MARA", "RIOT", "CLSK", "CIFR", "WULF", "IREN", "HUT", "BTDR", "CORZ"],
        "WGMI",
    ),
    theme(
        "crypto_equities",
        "Crypto Equities",
        "Macro",
        "Treasury, exchange, and broker names tied to crypto prices.",
        ["MSTR", "COIN", "HOOD", "CRCL", "GLXY", "MARA"],
    ),
    theme(
        "fintech",
        "Fintech",
        "Macro",
        "Consumer finance apps, brokers, and payments challengers.",
        ["PYPL", "HOOD", "COIN", "AFRM", "SOFI", "UPST", "NU", "TOST", "BILL", "XYZ"],
        "FINX",
    ),
    theme(
        "banks",
        "Banks",
        "Macro",
        "Money-center and super-regional banks.",
        ["JPM", "BAC", "WFC", "C", "GS", "MS", "USB", "PNC", "TFC", "COF"],
        "KBE",
    ),
    theme(
        "regional_banks",
        "Regional Banks",
        "Macro",
        "Regional lenders.",
        ["RF", "KEY", "FITB", "CFG", "HBAN", "ZION", "WAL", "MTB", "EWBC", "SSB"],
        "KRE",
    ),
    theme(
        "insurance_brokers",
        "Insurance Brokers",
        "Macro",
        "Commercial insurance brokers.",
        ["MRSH", "AON", "AJG", "WTW", "BRO", "RYAN", "ERIE"],
    ),
    theme(
        "oil",
        "Oil Producers",
        "Macro",
        "Integrated and independent oil and gas producers.",
        ["XOM", "CVX", "COP", "EOG", "OXY", "FANG", "DVN", "APA", "OVV", "PR"],
        "XOP",
    ),
    theme(
        "midstream",
        "Oil & Gas Midstream",
        "Macro",
        "Pipelines and midstream partnerships.",
        ["EPD", "ET", "WMB", "KMI", "OKE", "TRGP", "MPLX", "ENB"],
        "AMLP",
    ),
    theme(
        "shipping",
        "Marine Shipping",
        "Macro",
        "Container, dry bulk, and tanker owners.",
        ["ZIM", "DAC", "GSL", "SBLK", "STNG", "INSW", "FRO", "DHT", "MATX", "TRMD"],
        "BOAT",
    ),
    theme(
        "aerospace",
        "Aerospace",
        "Macro",
        "Airframes, engines, and aero suppliers.",
        ["BA", "GE", "RTX", "TDG", "HWM", "HEI", "TXT", "HXL", "CW", "ATI"],
    ),
    theme(
        "homebuilders",
        "Homebuilders",
        "Macro",
        "US production homebuilders.",
        ["DHI", "LEN", "PHM", "NVR", "TOL", "KBH", "MTH", "SKY"],
        "XHB",
    ),
    theme(
        "travel",
        "Travel",
        "Macro",
        "Booking, hotels, cruise, and airlines.",
        ["BKNG", "ABNB", "EXPE", "MAR", "HLT", "CCL", "RCL", "NCLH", "DAL", "UAL"],
    ),
    theme(
        "casinos",
        "Casinos",
        "Macro",
        "Casino operators and a sportsbook name.",
        ["LVS", "WYNN", "MGM", "CZR", "MLCO", "BYD", "PENN", "DKNG", "CHDN"],
    ),
    theme(
        "payments",
        "Payments",
        "Macro",
        "Card networks and merchant acquirers.",
        ["V", "MA", "AXP", "PYPL", "FIS", "FISV", "GPN", "TOST", "CPAY"],
        "IPAY",
    ),
    theme(
        "reshoring",
        "Reshoring",
        "Macro",
        "Machinery and electrical names tied to factory construction in the US.",
        ["CAT", "DE", "EMR", "ETN", "PH", "URI", "CMI", "PCAR", "HON", "ROK"],
    ),
    theme(
        "water",
        "Water",
        "Macro",
        "Regulated water utilities and water equipment.",
        ["AWK", "WTRG", "XYL", "ECL", "PNR", "VLTO", "FELE", "AWR", "WMS"],
    ),
    theme(
        "waste",
        "Waste",
        "Macro",
        "Solid-waste and environmental-services operators.",
        ["WM", "RSG", "WCN", "CLH", "CWST", "GFL"],
    ),
    theme(
        "rail",
        "Railroads",
        "Macro",
        "North American freight rails and a rail-equipment name.",
        ["UNP", "CSX", "NSC", "CP", "CNI", "WAB", "GBX", "TRN"],
    ),
    theme(
        "trucking",
        "Trucking",
        "Macro",
        "Truckload and less-than-truckload carriers.",
        ["ODFL", "SAIA", "XPO", "JBHT", "KNX", "ARCB", "TFII", "WERN"],
    ),
    theme(
        "steel",
        "Steel",
        "Macro",
        "US steel and service-center names.",
        ["NUE", "STLD", "CLF", "RS", "CMC", "MT", "GGB"],
        "SLX",
    ),
]


def validate_catalog(themes: list[dict] | None = None) -> None:
    rows = THEMES if themes is None else themes
    seen: set[str] = set()
    for row in rows:
        theme_id = row["id"]
        if theme_id in seen:
            raise ValueError(f"duplicate theme id: {theme_id}")
        seen.add(theme_id)
        if row["lane"] not in LANE_ORDER:
            raise ValueError(f"{theme_id} has unknown lane {row['lane']}")
        tickers = row["tickers"]
        if len(tickers) < 3:
            raise ValueError(f"{theme_id} needs at least 3 tickers")
        if len(set(tickers)) != len(tickers):
            raise ValueError(f"{theme_id} repeats a ticker")
        for ticker in tickers:
            if not ticker or ticker != ticker.strip().upper():
                raise ValueError(f"{theme_id} has a bad ticker: {ticker!r}")


def unique_tickers(themes: list[dict] | None = None) -> list[str]:
    rows = THEMES if themes is None else themes
    ordered: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for ticker in row["tickers"]:
            if ticker not in seen:
                seen.add(ticker)
                ordered.append(ticker)
    return ordered


validate_catalog()
