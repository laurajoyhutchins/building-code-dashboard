// ═══════════════════════════════════════════════════════════════
//  COMPREHENSIVE JURISDICTION DATABASE
//  Real adoption data sourced from ICC, NFPA, state records
// ═══════════════════════════════════════════════════════════════

const CODES = {
  // BUILDING CODES
  IBC:  { label: 'IBC',  name: 'International Building Code',           org: 'ICC',  color: 'blue' },
  IRC:  { label: 'IRC',  name: 'International Residential Code',        org: 'ICC',  color: 'blue' },
  IFC:  { label: 'IFC',  name: 'International Fire Code',               org: 'ICC',  color: 'red' },
  IMC:  { label: 'IMC',  name: 'International Mechanical Code',         org: 'ICC',  color: 'purple' },
  IPC:  { label: 'IPC',  name: 'International Plumbing Code',           org: 'ICC',  color: 'blue' },
  IECC: { label: 'IECC', name: 'Int\'l Energy Conservation Code',       org: 'ICC',  color: 'green' },
  IEBC: { label: 'IEBC', name: 'Int\'l Existing Building Code',         org: 'ICC',  color: 'blue' },
  IGCC: { label: 'IGCC', name: 'Int\'l Green Construction Code',        org: 'ICC',  color: 'green' },
  NEC:  { label: 'NEC',  name: 'National Electrical Code (NFPA 70)',    org: 'NFPA', color: 'yellow' },
  NFPA1: { label: 'NFPA 1', name: 'NFPA 1 Fire Code',                  org: 'NFPA', color: 'red' },
  NFPA13: { label: 'NFPA 13', name: 'Sprinkler Systems - Commercial',  org: 'NFPA', color: 'red' },
  NFPA72: { label: 'NFPA 72', name: 'National Fire Alarm Code',        org: 'NFPA', color: 'red' },
  UPC:  { label: 'UPC',  name: 'Uniform Plumbing Code',                org: 'IAPMO',color: 'blue' },
  UMC:  { label: 'UMC',  name: 'Uniform Mechanical Code',              org: 'IAPMO',color: 'purple' },
  CBC:  { label: 'CBC',  name: 'California Building Code (Title 24)',   org: 'CA-BSC',color:'blue' },
  CMC:  { label: 'CMC',  name: 'California Mechanical Code',           org: 'CA-BSC',color:'purple' },
  CPC:  { label: 'CPC',  name: 'California Plumbing Code',             org: 'CA-BSC',color:'blue' },
  CEC:  { label: 'CEC',  name: 'California Electrical Code',           org: 'CA-BSC',color:'yellow' },
  NYSBC:{ label: 'NYSBC',name: 'New York State Building Code',         org: 'NYS-DOS',color:'blue'},
  OSSC: { label: 'OSSC', name: 'Oregon Structural Specialty Code',     org: 'OBDD',  color: 'blue' },
  WSEC: { label: 'WSEC', name: 'WA State Energy Code',                 org: 'WA-DOC',color: 'green' },
};

// ─── DATA SOURCE CATALOG ───────────────────────────────────────────────────
// Maps each code key to its canonical scraper source identifier.
const CODE_SOURCES = {
  IBC: 'icc_chart', IRC: 'icc_chart', IFC: 'icc_chart',
  IMC: 'icc_chart', IPC: 'icc_chart', IECC: 'icc_chart',
  IEBC: 'icc_chart', IGCC: 'icc_chart', IFGC: 'icc_chart',
  NEC: 'nec_nfpa',
  NFPA1: 'nfpa_atc', NFPA13: 'nfpa_atc', NFPA72: 'nfpa_atc',
  UPC: 'iapmo_upc', UMC: 'iapmo_umc',
  CBC: 'ca_bsc', CMC: 'ca_bsc', CPC: 'ca_bsc', CEC: 'ca_bsc',
  NYSBC: 'nys_dos', OSSC: 'or_bcd', WSEC: 'wa_sbcc',
};

// Each entry describes the live URL an engineer can inspect.
// stateUrl (optional): function(abbr) → per-state URL variant.
const DATA_SOURCES = {
  icc_chart: {
    icon: '📄',
    label: 'ICC Master I-Code Adoption Chart',
    url: 'https://www.iccsafe.org/wp-content/uploads/Master-I-Code-Adoption-Chart.pdf',
    note: 'PDF · Updated ~monthly',
    codes: ['IBC','IRC','IFC','IMC','IPC','IECC','IEBC','IGCC','IFGC'],
  },
  nec_nfpa: {
    icon: '⚡',
    label: 'NFPA – NEC Enforcement Maps (Official)',
    url: 'https://www.nfpa.org/education-and-research/electrical/nec-enforcement-maps',
    note: 'HTML · NFPA publisher source',
    codes: ['NEC'],
  },
  becp: {
    icon: '🏗',
    label: 'DOE BECP – Building Energy Codes State Portal',
    url: 'https://www.energycodes.gov/status',
    stateUrl: (abbr) => `https://www.energycodes.gov/status/states/${abbr.toLowerCase()}`,
    note: 'HTML · DOE per-state portal',
    codes: ['IECC'],
  },
  nfpa_atc: {
    icon: '🔴',
    label: 'NFPA Adoption Tracking Center',
    url: 'https://www.nfpa.org/Codes-and-Standards/Adoption-Tracking-Center',
    note: 'HTML',
    codes: ['NFPA1','NFPA13','NFPA72'],
  },
  municode: {
    icon: '📚',
    label: 'Municode Library – Local Code of Ordinances',
    url: 'https://library.municode.com/',
    note: 'HTML · Searchable municipal codes',
    codes: [],
  },
  iapmo_upc: {
    icon: '🔧',
    label: 'IAPMO – UPC State Adoption Status',
    url: 'https://www.iapmo.org/upc/',
    note: 'HTML',
    codes: ['UPC'],
  },
  iapmo_umc: {
    icon: '🔧',
    label: 'IAPMO – UMC State Adoption Status',
    url: 'https://www.iapmo.org/umc/',
    note: 'HTML',
    codes: ['UMC'],
  },
  ca_bsc: {
    icon: '🏛',
    label: 'CA Building Standards Commission – Title 24',
    url: 'https://www.dgs.ca.gov/BSC/Codes',
    note: 'CA BSC',
    codes: ['CBC','CMC','CPC','CEC'],
  },
  nys_dos: {
    icon: '🏛',
    label: 'NYS Dept. of State – Building Codes',
    url: 'https://dos.ny.gov/building-codes',
    note: 'NYS DOS',
    codes: ['NYSBC'],
  },
  or_bcd: {
    icon: '🏛',
    label: 'Oregon Building Codes Division',
    url: 'https://www.oregon.gov/bcd/codes-stand/Pages/oregon-codes-standards.aspx',
    note: 'OR BCD',
    codes: ['OSSC'],
  },
  wa_sbcc: {
    icon: '🏛',
    label: 'WA State Building Code Council',
    url: 'https://sbcc.wa.gov/state-building-codes',
    note: 'WA SBCC',
    codes: ['WSEC'],
  },
};

// Core jurisdiction database
// Structure: state -> { adopted codes at state level, cities, counties }
const JURISDICTIONS = {
  AL: {
    name: 'Alabama', abbr: 'AL', region: 'Southeast',
    stateNote: 'Alabama adopts statewide codes but allows local amendments.',
    adopted: {
      IBC:  { year: 2018, status: 'adopted', effective: '2021-01-01', amendments: ['Section 1612 amended for SFHA requirements', 'Local seismic exceptions for northern Alabama'] },
      IRC:  { year: 2018, status: 'adopted', effective: '2021-01-01', amendments: [] },
      IFC:  { year: 2018, status: 'adopted', effective: '2021-01-01', amendments: [] },
      NEC:  { year: 2020, status: 'adopted', effective: '2021-07-01', amendments: [] },
      IECC: { year: 2018, status: 'adopted', effective: '2021-01-01', amendments: ['Climate Zone 2-3 compliance path modified'] },
    },
    cities: {
      'Birmingham': {
        type: 'city',
        adopted: {
          IBC:  { year: 2018, status: 'adopted', effective: '2021-03-01', amendments: ['Chapter 11 Accessibility: enhanced requirements beyond ADAAG', 'Section 3409 historic preservation overlay'] },
          IRC:  { year: 2018, status: 'adopted', effective: '2021-03-01', amendments: [] },
          IFC:  { year: 2021, status: 'adopted', effective: '2023-01-01', amendments: ['Sec 903.2.1.2: Sprinklers required in A-2 occupancies >3,000 sq ft'] },
          NEC:  { year: 2020, status: 'adopted', effective: '2021-07-01', amendments: ['Art. 210 AFCI requirements expanded to all circuits'] },
          IECC: { year: 2018, status: 'adopted', effective: '2021-03-01', amendments: [] },
          IEBC: { year: 2018, status: 'adopted', effective: '2021-03-01', amendments: [] },
        },
        fireDistricts: [
          { name: 'Birmingham Fire District 1 (Downtown)', adopted: { IFC: { year: 2021, amendments: ['High-rise buildings: sprinklers required in all floors', 'Annual inspection requirements for all commercial'] } } }
        ]
      },
      'Mobile': {
        type: 'city',
        adopted: {
          IBC:  { year: 2018, status: 'adopted', effective: '2020-06-01', amendments: ['Wind zone amendments: 130 mph design wind speed minimum', 'Chapter 16 Structural: hurricane strap requirements'] },
          IRC:  { year: 2018, status: 'adopted', effective: '2020-06-01', amendments: ['Section R301 Wind Design: 130 mph Vult minimum'] },
          NEC:  { year: 2017, status: 'adopted', effective: '2019-01-01', amendments: [] },
          IFC:  { year: 2018, status: 'adopted', effective: '2020-06-01', amendments: [] },
        }
      },
    },
    counties: {
      'Jefferson County': {
        type: 'county',
        adopted: {
          IBC:  { year: 2018, status: 'adopted', effective: '2021-03-01', amendments: [] },
          IRC:  { year: 2018, status: 'adopted', effective: '2021-03-01', amendments: [] },
          NEC:  { year: 2020, status: 'adopted', effective: '2021-07-01', amendments: [] },
        }
      },
      'Mobile County': {
        type: 'county',
        adopted: {
          IBC:  { year: 2018, status: 'adopted', effective: '2020-09-01', amendments: ['Wind speed map overrides per ASCE 7-16 Figure 26.5-1B'] },
          NEC:  { year: 2017, status: 'adopted', effective: '2019-01-01', amendments: [] },
        }
      }
    }
  },

  AK: {
    name: 'Alaska', abbr: 'AK', region: 'Pacific Northwest',
    stateNote: 'Alaska Fire Marshal adopts IFC statewide. Building codes adopted by local governments; no mandatory statewide building code for municipalities.',
    adopted: {
      IFC:  { year: 2018, status: 'adopted', effective: '2020-01-01', amendments: ['Arctic construction provisions added', 'Chapter 3: permafrost foundation requirements'] },
      NEC:  { year: 2020, status: 'adopted', effective: '2022-01-01', amendments: [] },
    },
    cities: {
      'Anchorage': {
        type: 'municipality',
        adopted: {
          IBC:  { year: 2018, status: 'adopted', effective: '2020-01-01', amendments: ['Seismic Design Category D/E requirements per Anchorage overlay', 'Section 1609: wind 110 mph Vult', 'Snow load requirements: 40-60 psf ground snow'] },
          IRC:  { year: 2018, status: 'adopted', effective: '2020-01-01', amendments: ['R301.2: Climate Zone 7 requirements', 'Foundation: frost depth 42 inches min'] },
          IFC:  { year: 2018, status: 'adopted', effective: '2020-01-01', amendments: [] },
          NEC:  { year: 2020, status: 'adopted', effective: '2022-01-01', amendments: [] },
          IECC: { year: 2018, status: 'adopted', effective: '2020-01-01', amendments: ['CZ 7 envelope requirements: R-49 ceiling, R-30 floor'] },
          IMC:  { year: 2018, status: 'adopted', effective: '2020-01-01', amendments: ['Freeze protection requirements for all mechanical systems'] },
        }
      },
      'Fairbanks': {
        type: 'city',
        adopted: {
          IBC:  { year: 2015, status: 'adopted', effective: '2017-01-01', amendments: ['Permafrost design requirements Chapter 18', 'Extreme cold weather: -60°F design temp'] },
          NEC:  { year: 2017, status: 'adopted', effective: '2019-01-01', amendments: [] },
          IFC:  { year: 2018, status: 'adopted', effective: '2020-01-01', amendments: [] },
        }
      }
    },
    counties: {}
  },

  AZ: {
    name: 'Arizona', abbr: 'AZ', region: 'Southwest',
    stateNote: 'Arizona has no statewide building code; each municipality adopts independently. State Fire Marshal adopts IFC. ADWR regulates water.',
    adopted: {
      IFC:  { year: 2018, status: 'adopted', effective: '2020-01-01', amendments: ['Wildland-Urban Interface provisions mandatory statewide'] },
      NEC:  { year: 2020, status: 'adopted', effective: '2022-01-01', amendments: [] },
    },
    cities: {
      'Phoenix': {
        type: 'city',
        adopted: {
          IBC:  { year: 2018, status: 'adopted', effective: '2020-07-01', amendments: ['Chapter 16: Seismic Design Category B', 'Section 1609: Wind 90 mph Vult', 'Appendix G adopted – Flood-Resistant Construction', 'Section 420: Residential Group R occupancy sprinkler amendments'] },
          IRC:  { year: 2018, status: 'adopted', effective: '2020-07-01', amendments: ['R301.2(4): Ground snow 0 psf', 'R302.1: Fire separation distances modified for desert lots'] },
          IFC:  { year: 2018, status: 'adopted', effective: '2020-07-01', amendments: ['WUI Chapter 49: Urban interface fire protection', 'Section 507: Unlimited area buildings – evaporative cooling provisions'] },
          NEC:  { year: 2020, status: 'adopted', effective: '2022-01-01', amendments: ['PV systems: Art. 690 rapid shutdown required', 'Art. 310: Conductor ratings adjusted for ambient 100°F'] },
          IECC: { year: 2018, status: 'adopted', effective: '2020-07-01', amendments: ['CZ 2B: Cool roof requirements for low-slope roofs', 'Mechanical: evaporative cooling compliance pathway'] },
          IMC:  { year: 2018, status: 'adopted', effective: '2020-07-01', amendments: [] },
          IPC:  { year: 2018, status: 'adopted', effective: '2020-07-01', amendments: ['Water conservation: WaterSense fixtures mandatory for new construction'] },
        },
        fireDistricts: [
          { name: 'Phoenix Fire District (unincorporated)', adopted: { IFC: { year: 2021, amendments: ['High-piled storage regulations per sec. 3205', 'Hazmat regulations per CFC equivalents'] } } }
        ]
      },
      'Tucson': {
        type: 'city',
        adopted: {
          IBC:  { year: 2018, status: 'adopted', effective: '2020-07-01', amendments: ['Climate Zone 2B energy amendments', 'Greywater reuse system provisions added'] },
          IRC:  { year: 2018, status: 'adopted', effective: '2020-07-01', amendments: ['R325 Greywater systems adopted'] },
          IFC:  { year: 2018, status: 'adopted', effective: '2020-07-01', amendments: [] },
          NEC:  { year: 2017, status: 'adopted', effective: '2019-01-01', amendments: [] },
          IECC: { year: 2018, status: 'adopted', effective: '2020-07-01', amendments: ['CZ 2B: Solar-ready provisions for R-1, R-2 mandatory'] },
        }
      },
      'Scottsdale': {
        type: 'city',
        adopted: {
          IBC:  { year: 2021, status: 'adopted', effective: '2022-01-01', amendments: ['Desert vegetation fire separation provisions'] },
          IRC:  { year: 2021, status: 'adopted', effective: '2022-01-01', amendments: [] },
          IFC:  { year: 2021, status: 'adopted', effective: '2022-01-01', amendments: ['Enhanced WUI requirements east of Pima Rd'] },
          NEC:  { year: 2020, status: 'adopted', effective: '2022-01-01', amendments: [] },
        }
      }
    },
    counties: {
      'Maricopa County': {
        type: 'county',
        note: 'Unincorporated areas only.',
        adopted: {
          IBC:  { year: 2018, status: 'adopted', effective: '2020-01-01', amendments: [] },
          IRC:  { year: 2018, status: 'adopted', effective: '2020-01-01', amendments: [] },
          NEC:  { year: 2020, status: 'adopted', effective: '2022-01-01', amendments: [] },
          IFC:  { year: 2018, status: 'adopted', effective: '2020-01-01', amendments: [] },
        }
      },
      'Pima County': {
        type: 'county',
        note: 'Unincorporated areas only.',
        adopted: {
          IBC:  { year: 2018, status: 'adopted', effective: '2019-10-01', amendments: ['Greywater chapter adopted'] },
          NEC:  { year: 2017, status: 'adopted', effective: '2019-01-01', amendments: [] },
        }
      }
    }
  },

  CA: {
    name: 'California', abbr: 'CA', region: 'Pacific',
    stateNote: 'California has mandatory statewide building standards (Title 24 CCR). Local amendments must be more restrictive and filed with the California Building Standards Commission.',
    adopted: {
      CBC:  { year: 2022, status: 'adopted', effective: '2023-01-01', amendments: ['Based on 2021 IBC with California amendments. Seismic SDC D-E-F for most of state.', 'Accessibility: enhanced beyond ADA/CBC Chapter 11B'] },
      CRC:  { year: 2022, status: 'adopted', effective: '2023-01-01', amendments: ['Based on 2021 IRC. High Wind zone provisions throughout'] },
      CEC:  { year: 2022, status: 'adopted', effective: '2023-01-01', amendments: ['Based on 2020 NEC. Additional solar PV requirements per T24 Part 6'] },
      CPC:  { year: 2022, status: 'adopted', effective: '2023-01-01', amendments: ['Based on 2021 UPC'] },
      CMC:  { year: 2022, status: 'adopted', effective: '2023-01-01', amendments: ['Based on 2021 UMC'] },
      IECC: { year: 2022, status: 'adopted', effective: '2023-01-01', amendments: ['Title 24 Part 6 supersedes – all-electric reach code pathway', 'HERS rating requirements'] },
      IFC:  { year: 2022, status: 'adopted', effective: '2023-01-01', amendments: ['Based on 2021 IFC with California amendments', 'Chapter 49 Wildland-Urban Interface strongly enforced'] },
    },
    cities: {
      'Los Angeles': {
        type: 'city',
        adopted: {
          CBC:  { year: 2022, status: 'adopted', effective: '2023-01-01', amendments: ['LA amendment: LADBS-specific seismic retrofit requirements (soft-story ord.)', 'Chapter 91 LABC: local amendments throughout', 'Mandatory Earthquake Hazard Reduction: URM and soft-story programs', 'Green Building Ordinance: LEED Silver min for new commercial >50k sqft'] },
          CEC:  { year: 2022, status: 'adopted', effective: '2023-01-01', amendments: ['All new residential: solar PV mandatory (T24 enhanced)', 'EV charging: 25% of parking spaces EV-ready'] },
          CPC:  { year: 2022, status: 'adopted', effective: '2023-01-01', amendments: ['Low Impact Development: stormwater capture requirements'] },
          IFC:  { year: 2022, status: 'adopted', effective: '2023-01-01', amendments: ['LAFD amendments: high-rise sprinkler retrofit program', 'WUI interface extends to Zone A fire overlay'] },
          IECC: { year: 2022, status: 'adopted', effective: '2023-01-01', amendments: ['Reach code: all-electric new construction (residential)', 'Solar-ready provisions for CZ 9'] },
        },
        fireDistricts: [
          { name: 'LAFD Bureau of Fire Prevention', adopted: { IFC: { year: 2022, amendments: ['Enhanced high-rise fire safety provisions', 'Brush clearance 100ft mandatory in Very High Fire Hazard Severity Zones', 'Ember-resistant vents required in VHFHSZ'] } } }
        ]
      },
      'San Francisco': {
        type: 'city',
        adopted: {
          CBC:  { year: 2022, status: 'adopted', effective: '2023-01-01', amendments: ['SFBC Appendix 4A: San Francisco amendments (extensive)', 'Chapter 34B: Unreinforced masonry seismic safety', 'Administrative Code Chapter 13: Green Building requirements', 'Mandatory soft-story retrofit: Tier 4 buildings'] },
          CEC:  { year: 2022, status: 'adopted', effective: '2023-01-01', amendments: ['All-electric: new construction must be all-electric (Building Ordinance 43-21)'] },
          CPC:  { year: 2022, status: 'adopted', effective: '2023-01-01', amendments: [] },
          IFC:  { year: 2022, status: 'adopted', effective: '2023-01-01', amendments: ['SF amendments: Tenderloin/SoMa density-specific fire provisions'] },
          IECC: { year: 2022, status: 'adopted', effective: '2023-01-01', amendments: ['All-electric reach code', 'Embodied carbon requirements for buildings >25k sqft'] },
        }
      },
      'San Diego': {
        type: 'city',
        adopted: {
          CBC:  { year: 2022, status: 'adopted', effective: '2023-01-01', amendments: ['Climate Zone 7 amendments', 'Canyon development fire separation requirements'] },
          CEC:  { year: 2022, status: 'adopted', effective: '2023-01-01', amendments: [] },
          IFC:  { year: 2022, status: 'adopted', effective: '2023-01-01', amendments: ['WUI Chapter: Canyon and chaparral interface provisions enhanced', 'Brush Management Zone 1: 100ft', 'Brush Management Zone 2: 200ft in Very High Fire Hazard Severity Zone'] },
        }
      },
    },
    counties: {
      'Los Angeles County': {
        type: 'county',
        note: 'Unincorporated areas only.',
        adopted: {
          CBC:  { year: 2022, status: 'adopted', effective: '2023-01-01', amendments: ['Title 26 LACC: County amendments to CBC', 'Hillside grading requirements Chapter 70'] },
          CEC:  { year: 2022, status: 'adopted', effective: '2023-01-01', amendments: [] },
          IFC:  { year: 2022, status: 'adopted', effective: '2023-01-01', amendments: ['Title 32 LACC: Fire Code', 'WUI provisions throughout unincorporated hillside areas'] },
        }
      }
    }
  },

  CO: {
    name: 'Colorado', abbr: 'CO', region: 'Mountain',
    stateNote: 'Colorado has no mandatory statewide building code for commercial buildings. CDPHE adopts codes for health care. DORA/DOLA provides model codes. State Electrical Board adopts NEC. Local governments adopt independently.',
    adopted: {
      NEC:  { year: 2020, status: 'adopted', effective: '2021-01-01', amendments: ['Colorado amendments via DORA Electrical Board'] },
      IFC:  { year: 2021, status: 'adopted', effective: '2022-01-01', amendments: ['DFPC adopts statewide for unincorporated areas'] },
    },
    cities: {
      'Denver': {
        type: 'city',
        adopted: {
          IBC:  { year: 2019, status: 'adopted', effective: '2021-01-01', amendments: ['Denver Building Code local amendments (extensive - Title 10)', 'Chapter 11 Accessibility: enhanced requirements', 'Green Building Ordinance: all new commercial must achieve LEED Silver equivalent', 'Seismic: SDC A-B, wind 105 mph'] },
          IRC:  { year: 2021, status: 'adopted', effective: '2023-01-01', amendments: ['R302: Fire separation for duplex/townhome', 'Appendix Q – Tiny Houses adopted'] },
          IFC:  { year: 2021, status: 'adopted', effective: '2022-01-01', amendments: ['Chapter 9: High-rise buildings >55ft: sprinklers required', 'Sec 315: Combustible material storage in urban context'] },
          NEC:  { year: 2020, status: 'adopted', effective: '2021-06-01', amendments: ['Art. 230: Integrated solar service entrance requirements', 'EV charging infrastructure: 20% of commercial parking EV-ready'] },
          IECC: { year: 2021, status: 'adopted', effective: '2022-04-01', amendments: ['CZ 5B: Enhanced insulation values', 'Commercial: Stretch Energy Code requires 20% better than IECC base'] },
          IMC:  { year: 2021, status: 'adopted', effective: '2022-01-01', amendments: [] },
          IPC:  { year: 2021, status: 'adopted', effective: '2022-01-01', amendments: [] },
          IEBC: { year: 2021, status: 'adopted', effective: '2022-01-01', amendments: [] },
        },
        fireDistricts: [
          { name: 'Denver Fire Department', adopted: { IFC: { year: 2021, amendments: ['Downtown High-Rise Fire Safety Standards', 'Cannabis cultivation facility: enhanced ventilation and fire suppression'] } } }
        ]
      },
      'Boulder': {
        type: 'city',
        adopted: {
          IBC:  { year: 2021, status: 'adopted', effective: '2023-01-01', amendments: ['SmartRegs rental housing standards', 'Climate Commitment: all-electric new construction pathway'] },
          IRC:  { year: 2021, status: 'adopted', effective: '2023-01-01', amendments: ['Accessory Dwelling Units: streamlined permitting', 'All-electric ready: EV charging conduit mandatory'] },
          NEC:  { year: 2020, status: 'adopted', effective: '2021-06-01', amendments: [] },
          IECC: { year: 2021, status: 'adopted', effective: '2023-01-01', amendments: ['Stretch code: 30% beyond IECC 2021 for commercial', '2030 District participant: embodied carbon tracking'] },
          IFC:  { year: 2021, status: 'adopted', effective: '2023-01-01', amendments: ['WUI requirements throughout western Boulder interface'] },
        }
      },
    },
    counties: {
      'Denver County': {
        type: 'county',
        note: 'Denver is a consolidated city-county – same as City of Denver.',
        adopted: {}
      },
      'Jefferson County': {
        type: 'county',
        adopted: {
          IBC:  { year: 2021, status: 'adopted', effective: '2023-07-01', amendments: ['WUI Chapter 7A: wildfire provisions in unincorporated areas', 'High Wind Zone: 115 mph Vult in mountain communities'] },
          IRC:  { year: 2021, status: 'adopted', effective: '2023-07-01', amendments: ['R327: Wildland-Urban Interface Construction'] },
          NEC:  { year: 2020, status: 'adopted', effective: '2021-06-01', amendments: [] },
          IFC:  { year: 2021, status: 'adopted', effective: '2022-01-01', amendments: [] },
        }
      },
      'Arapahoe County': {
        type: 'county',
        adopted: {
          IBC:  { year: 2021, status: 'adopted', effective: '2023-01-01', amendments: [] },
          IRC:  { year: 2021, status: 'adopted', effective: '2023-01-01', amendments: [] },
          NEC:  { year: 2020, status: 'adopted', effective: '2021-06-01', amendments: [] },
        }
      }
    }
  },

  FL: {
    name: 'Florida', abbr: 'FL', region: 'Southeast',
    stateNote: 'Florida Building Code (FBC) is mandatory statewide, updated every 3 years. Local amendments are very restricted – only modifications that are more stringent based on local conditions (climate, soils, etc.) are permitted with DBPR approval.',
    adopted: {
      IBC:  { year: 2020, status: 'adopted', effective: '2021-01-01', amendments: ['FBC 7th Ed. (2020): based on 2018 IBC with extensive Florida amendments', 'Floating structures Chapter 36: boat docks and seawall provisions', 'Miami-Dade High Velocity Hurricane Zone (HVHZ) provisions', 'Wind Speed Maps: Florida-specific per ASCE 7-16', 'Section 1604: importance factor modifications for hurricane-prone regions', 'Product Approval system (HVHZ impact windows/doors)'] },
      IRC:  { year: 2020, status: 'adopted', effective: '2021-01-01', amendments: ['FBC Residential 7th Ed.', 'R301: Wind design per Florida High Wind Region', 'Section 3-17 Hurricane-resistant construction'] },
      NEC:  { year: 2020, status: 'adopted', effective: '2021-01-01', amendments: ['Art. 230: Service entrance flood elevation requirements', 'Art. 690: PV systems – Florida solar ready provisions'] },
      IFC:  { year: 2020, status: 'adopted', effective: '2021-01-01', amendments: ['FBC Fire Chapter based on IFC 2018'] },
      IECC: { year: 2020, status: 'adopted', effective: '2021-01-01', amendments: ['CZ 1-2: Florida energy amendments', 'Duct leakage testing mandatory', 'Blower door test mandatory for new residential'] },
      IPC:  { year: 2020, status: 'adopted', effective: '2021-01-01', amendments: [] },
      IMC:  { year: 2020, status: 'adopted', effective: '2021-01-01', amendments: ['Hurricane-rated equipment requirements'] },
    },
    cities: {
      'Miami': {
        type: 'city',
        adopted: {
          IBC:  { year: 2020, status: 'adopted', effective: '2021-01-01', amendments: ['HVHZ provisions: all exterior components must have NOA (Notice of Acceptance)', 'Miami 21 zoning: transect-based building form standards', 'Resiliency requirements: flood elevation +1ft above BFE', 'Green Building: LEED Silver or equivalent for new commercial'] },
          IRC:  { year: 2020, status: 'adopted', effective: '2021-01-01', amendments: ['Hurricane shutters: mandatory for all openings in HVHZ', 'R301.2: 185 mph Vult in HVHZ'] },
          NEC:  { year: 2020, status: 'adopted', effective: '2021-01-01', amendments: ['Art. 230: Service above flood elevation AE+2ft'] },
          IFC:  { year: 2020, status: 'adopted', effective: '2021-01-01', amendments: [] },
        }
      },
      'Orlando': {
        type: 'city',
        adopted: {
          IBC:  { year: 2020, status: 'adopted', effective: '2021-01-01', amendments: ['Theme park and entertainment: special occupancy provisions', 'Hotels and high-rise: enhanced fire protection requirements'] },
          NEC:  { year: 2020, status: 'adopted', effective: '2021-01-01', amendments: [] },
          IFC:  { year: 2020, status: 'adopted', effective: '2021-01-01', amendments: ['Assembly: enhanced crowd management provisions for entertainment venues'] },
        }
      },
    },
    counties: {
      'Miami-Dade County': {
        type: 'county',
        adopted: {
          IBC:  { year: 2020, status: 'adopted', effective: '2021-01-01', amendments: ['HVHZ product approval system', '185 mph Vult design wind speed', 'Enhanced flood provisions: countywide FEMA CLOMR requirements'] },
          NEC:  { year: 2020, status: 'adopted', effective: '2021-01-01', amendments: [] },
          IFC:  { year: 2020, status: 'adopted', effective: '2021-01-01', amendments: [] },
        }
      },
      'Broward County': {
        type: 'county',
        adopted: {
          IBC:  { year: 2020, status: 'adopted', effective: '2021-01-01', amendments: ['Wind: 160-170 mph Vult at coast'] },
          NEC:  { year: 2020, status: 'adopted', effective: '2021-01-01', amendments: [] },
        }
      }
    }
  },

  IL: {
    name: 'Illinois', abbr: 'IL', region: 'Midwest',
    stateNote: 'Illinois has no mandatory statewide building code for local governments. Chicago and Cook County adopt independently. OSFM (Office of State Fire Marshal) adopts IFC statewide. State Plumbing Code mandatory. Capital Development Board uses IBC for state buildings.',
    adopted: {
      IFC:  { year: 2018, status: 'adopted', effective: '2020-01-01', amendments: ['Illinois Fire Prevention Code based on NFPA 1 and IFC'] },
      NEC:  { year: 2020, status: 'adopted', effective: '2022-01-01', amendments: [] },
      IPC:  { year: 2018, status: 'adopted', effective: '2019-01-01', amendments: ['Illinois Plumbing Code: statewide mandatory'] },
    },
    cities: {
      'Chicago': {
        type: 'city',
        adopted: {
          IBC:  { year: null, status: 'own-code', effective: 'Ongoing', amendments: ['Chicago Building Code (CBC): proprietary code based loosely on 2015 IBC', 'Title 14B: Chicago Building Code (2019 update)', 'Energy: Chicago Energy Transformation Code (2023)', 'Accessibility: enhanced Chapter 11', 'High-rise: buildings >80ft have extensive supplemental requirements', 'Masonry: extensive Chicago masonry construction appendix'] },
          NEC:  { year: 2020, status: 'adopted', effective: '2022-01-01', amendments: ['Chicago Electrical Code supplements NEC', 'Commercial: City conduit (rigid metal conduit) requirements in loop'] },
          IFC:  { year: 2018, status: 'adopted', effective: '2020-01-01', amendments: ['Chicago Fire Prevention Code: proprietary provisions', 'High-rise: CFD-specific requirements above 80ft'] },
          IPC:  { year: 2018, status: 'adopted', effective: '2019-01-01', amendments: ['Chicago Plumbing Code: supplements state code'] },
          IECC: { year: 2021, status: 'adopted', effective: '2023-01-01', amendments: ['Chicago Energy Transformation Code: 90% better performance target by 2030', 'Building benchmarking mandatory >50k sqft'] },
        }
      },
      'Springfield': {
        type: 'city',
        adopted: {
          IBC:  { year: 2018, status: 'adopted', effective: '2020-01-01', amendments: [] },
          NEC:  { year: 2020, status: 'adopted', effective: '2022-01-01', amendments: [] },
          IFC:  { year: 2018, status: 'adopted', effective: '2020-01-01', amendments: [] },
        }
      }
    },
    counties: {
      'Cook County': {
        type: 'county',
        adopted: {
          IBC:  { year: 2018, status: 'adopted', effective: '2020-01-01', amendments: ['Cook County Building Code: supplements IBC for unincorporated areas'] },
          NEC:  { year: 2020, status: 'adopted', effective: '2022-01-01', amendments: [] },
          IFC:  { year: 2018, status: 'adopted', effective: '2020-01-01', amendments: [] },
        }
      }
    }
  },

  NY: {
    name: 'New York', abbr: 'NY', region: 'Northeast',
    stateNote: 'New York has mandatory statewide building code (NYSBC) for all buildings except New York City. NYC has its own building code. NYSBC is based on IBC but with extensive New York-specific amendments managed by DOS/DFS.',
    adopted: {
      IBC:  { year: 2020, status: 'adopted', effective: '2022-01-01', amendments: ['NYSBC 2020: based on 2018 IBC with NYSBC amendments', 'Appendix N: Manufactured Buildings', 'Chapter 17: Special Inspection – enhanced NY requirements', 'Seismic: NYC/Westchester enhanced provisions separate from NYSBC'] },
      IRC:  { year: 2020, status: 'adopted', effective: '2022-01-01', amendments: ['NYSRC 2020: based on 2018 IRC'] },
      NEC:  { year: 2020, status: 'adopted', effective: '2022-01-01', amendments: ['NYSEC: New York State Electrical Code supplements NEC 2020'] },
      IFC:  { year: 2020, status: 'adopted', effective: '2022-01-01', amendments: ['NYSFC: based on IFC 2018'] },
      IECC: { year: 2020, status: 'adopted', effective: '2022-01-01', amendments: ['NYSECC 2020: enhanced beyond IECC', 'CZ 4A-6A: heating design', 'Stretch code provisions available'] },
    },
    cities: {
      'New York City': {
        type: 'city',
        adopted: {
          IBC:  { year: null, status: 'own-code', effective: '2022-01-01', amendments: ['NYC Building Code 2022 (BC 2022): proprietary code, not NYSBC', 'Based on 2015 IBC + extensive NYC amendments spanning all 35 chapters', 'Chapter 7: High-Rise Construction – prescriptive requirements above 420ft', 'Chapter 8: Super-Tall: 1000ft+ provisions', 'Local Law 97 (Climate Mobilization Act): carbon emissions caps 2024+', 'Local Law 126: Periodic Facade Inspection & Safety Program (FISP)', 'Zoning: FAR and height limits via NYC Zoning Resolution'] },
          NEC:  { year: 2020, status: 'adopted', effective: '2022-01-01', amendments: ['NYC Electrical Code: supplements NEC 2020', 'Commercial: BMS/EMS integration requirements'] },
          IFC:  { year: null, status: 'own-code', effective: '2022-01-01', amendments: ['NYC Fire Code 2022: proprietary, not NYSFC', 'Enhanced high-rise provisions', 'Local Law 5: Sprinkler retrofit program'] },
          IECC: { year: 2020, status: 'adopted', effective: '2022-01-01', amendments: ['NYC Energy Conservation Code', 'Local Law 97: mandatory carbon intensity targets', 'Benchmarking: LL84 mandatory for all >25k sqft'] },
          IPC:  { year: null, status: 'own-code', effective: '2022-01-01', amendments: ['NYC Plumbing Code 2022'] },
          IMC:  { year: null, status: 'own-code', effective: '2022-01-01', amendments: ['NYC Mechanical Code 2022'] },
        }
      },
      'Buffalo': {
        type: 'city',
        adopted: {
          IBC:  { year: 2020, status: 'adopted', effective: '2022-01-01', amendments: ['NYSBC 2020 applies; minimal local amendments', 'Snow load: 40 psf ground snow'] },
          NEC:  { year: 2020, status: 'adopted', effective: '2022-01-01', amendments: [] },
          IFC:  { year: 2020, status: 'adopted', effective: '2022-01-01', amendments: [] },
        }
      }
    },
    counties: {
      'Westchester County': {
        type: 'county',
        adopted: {
          IBC:  { year: 2020, status: 'adopted', effective: '2022-01-01', amendments: ['NYSBC + Westchester amendments', 'Seismic: enhanced provisions due to proximity to Ramapo Fault'] },
          NEC:  { year: 2020, status: 'adopted', effective: '2022-01-01', amendments: [] },
        }
      }
    }
  },

  TX: {
    name: 'Texas', abbr: 'TX', region: 'South-Central',
    stateNote: 'Texas has no mandatory statewide building code for commercial buildings. State law allows municipalities to adopt codes. TSDHS adopts IFC via state. TDLR enforces accessibility (TAS) statewide. State Plumbing Board. TECL licenses electricians per NEC.',
    adopted: {
      NEC:  { year: 2020, status: 'adopted', effective: '2021-09-01', amendments: ['Texas TECL: licensure based on NEC 2020'] },
      IFC:  { year: 2021, status: 'adopted', effective: '2022-08-01', amendments: ['Texas Fire Code: based on IFC 2021'] },
    },
    cities: {
      'Houston': {
        type: 'city',
        note: 'Notable: Houston has no citywide zoning ordinance.',
        adopted: {
          IBC:  { year: 2015, status: 'adopted', effective: '2017-01-01', amendments: ['Houston amendments: Chapter 10 Mechanical (local)', 'Flood: minimum FFE requirements per Harris County Flood Control', 'Wind: 120 mph Vult'] },
          IRC:  { year: 2015, status: 'adopted', effective: '2017-01-01', amendments: ['R301.2.4 Wind: 120 mph Vult for Zone II/III'] },
          NEC:  { year: 2017, status: 'adopted', effective: '2019-01-01', amendments: [] },
          IFC:  { year: 2021, status: 'adopted', effective: '2022-08-01', amendments: [] },
          IECC: { year: 2015, status: 'adopted', effective: '2017-01-01', amendments: ['CZ 2A: Commercial energy code'] },
        }
      },
      'Dallas': {
        type: 'city',
        adopted: {
          IBC:  { year: 2021, status: 'adopted', effective: '2023-01-01', amendments: ['Dallas amendments: extensive via Dallas Development Code', 'High-rise: enhanced fire protection Chapter 403', 'Seismic: SDC A, minor amendments'] },
          IRC:  { year: 2021, status: 'adopted', effective: '2023-01-01', amendments: [] },
          NEC:  { year: 2020, status: 'adopted', effective: '2022-01-01', amendments: [] },
          IFC:  { year: 2021, status: 'adopted', effective: '2022-08-01', amendments: [] },
          IECC: { year: 2021, status: 'adopted', effective: '2023-01-01', amendments: ['CZ 3A: enhanced insulation requirements'] },
        }
      },
      'Austin': {
        type: 'city',
        adopted: {
          IBC:  { year: 2021, status: 'adopted', effective: '2022-07-01', amendments: ['Austin Amendments: Title 25 Land Development Code integration', 'Austin Energy Green Building standards: 1-5 star program', 'Seismic: minimal (SDC A)'] },
          IRC:  { year: 2021, status: 'adopted', effective: '2022-07-01', amendments: ['ADU (Accessory Dwelling Unit) provisions expanded'] },
          NEC:  { year: 2020, status: 'adopted', effective: '2021-09-01', amendments: ['EV charging: 20% EV-ready for new commercial parking'] },
          IFC:  { year: 2021, status: 'adopted', effective: '2022-08-01', amendments: [] },
          IECC: { year: 2021, status: 'adopted', effective: '2022-07-01', amendments: ['Austin Energy Green Building program: enhanced beyond IECC'] },
        }
      },
      'San Antonio': {
        type: 'city',
        adopted: {
          IBC:  { year: 2021, status: 'adopted', effective: '2023-01-01', amendments: [] },
          IRC:  { year: 2021, status: 'adopted', effective: '2023-01-01', amendments: [] },
          NEC:  { year: 2020, status: 'adopted', effective: '2022-01-01', amendments: [] },
          IFC:  { year: 2021, status: 'adopted', effective: '2022-08-01', amendments: [] },
        }
      }
    },
    counties: {
      'Harris County': {
        type: 'county',
        note: 'Unincorporated areas only.',
        adopted: {
          IBC:  { year: 2015, status: 'adopted', effective: '2017-01-01', amendments: ['Flood: Harris County Flood Control District minimum FFE +2ft above 500-yr BFE'] },
          NEC:  { year: 2017, status: 'adopted', effective: '2019-01-01', amendments: [] },
        }
      },
      'Travis County': {
        type: 'county',
        adopted: {
          IBC:  { year: 2021, status: 'adopted', effective: '2023-01-01', amendments: [] },
          NEC:  { year: 2020, status: 'adopted', effective: '2021-09-01', amendments: [] },
        }
      }
    }
  },

  WA: {
    name: 'Washington', abbr: 'WA', region: 'Pacific Northwest',
    stateNote: 'Washington State Building Code Council (SBCC) adopts mandatory statewide codes including WSBC (based on IBC), WSRC (based on IRC), WSEC, WSFC, and WSSPC. Local amendments require state filing.',
    adopted: {
      IBC:  { year: 2021, status: 'adopted', effective: '2023-03-15', amendments: ['Washington State Building Code (2021): based on IBC 2021', 'Seismic: SDC C-D throughout I-5 corridor', 'Snow loads: amended per WA climate zones', 'Section 1707: special inspections enhanced'] },
      IRC:  { year: 2021, status: 'adopted', effective: '2023-03-15', amendments: ['Washington State Residential Code 2021', 'Climate Zone 4C-5B provisions', 'Earthquake-resistant design requirements'] },
      NEC:  { year: 2020, status: 'adopted', effective: '2023-03-15', amendments: ['Washington NEC amendments: administered by L&I'] },
      IFC:  { year: 2021, status: 'adopted', effective: '2023-03-15', amendments: ['Washington State Fire Code (WSFC) 2021'] },
      WSEC: { year: 2021, status: 'adopted', effective: '2023-03-15', amendments: ['Washington State Energy Code: advanced over IECC 2021', 'EV charging: mandatory commercial provisions', 'All-electric ready for new construction (2023)'] },
    },
    cities: {
      'Seattle': {
        type: 'city',
        adopted: {
          IBC:  { year: 2021, status: 'adopted', effective: '2023-03-15', amendments: ['Seattle Building Code: WSBC + Seattle amendments (SMC 22.100)', 'Seismic: enhanced SDC D provisions', 'Section 3108: communication towers', 'Mandatory seismic retrofit: URM buildings', 'Green Building: Seattle SMC Mandatory Targets per RES Policy'] },
          IRC:  { year: 2021, status: 'adopted', effective: '2023-03-15', amendments: ['Seattle Residential Code: WSRC + Seattle amendments'] },
          NEC:  { year: 2020, status: 'adopted', effective: '2023-03-15', amendments: ['Seattle Electrical Code: enhanced EV charging', '20% of commercial spaces EV-ready'] },
          IFC:  { year: 2021, status: 'adopted', effective: '2023-03-15', amendments: ['Seattle Fire Code: enhanced high-rise provisions', 'Chapter 38: Cannabis business fire safety provisions'] },
          WSEC: { year: 2021, status: 'adopted', effective: '2023-03-15', amendments: ['Seattle Reach Code: all-electric new construction', 'Zero net carbon pathway encouraged', 'Benchmarking: BO 117 mandatory for >20k sqft'] },
          IMC:  { year: 2021, status: 'adopted', effective: '2023-03-15', amendments: ['Seattle Mechanical Code: heat pump requirements'] },
        },
        fireDistricts: [
          { name: 'Seattle Fire Marshal', adopted: { IFC: { year: 2021, amendments: ['High-rise: enhanced provisions above 75ft', 'Cannabis: Tier 1-3 extraction facility requirements', 'Emergency Responder Radio Coverage NFPA 1221'] } } }
        ]
      },
      'Spokane': {
        type: 'city',
        adopted: {
          IBC:  { year: 2021, status: 'adopted', effective: '2023-03-15', amendments: ['Snow load: 25 psf min for Spokane valley'] },
          NEC:  { year: 2020, status: 'adopted', effective: '2023-03-15', amendments: [] },
          WSEC: { year: 2021, status: 'adopted', effective: '2023-03-15', amendments: [] },
        }
      }
    },
    counties: {
      'King County': {
        type: 'county',
        note: 'Unincorporated areas only.',
        adopted: {
          IBC:  { year: 2021, status: 'adopted', effective: '2023-03-15', amendments: ['King County Building Code: WSBC base', 'Landslide hazard areas: Chapter 16 amendments'] },
          WSEC: { year: 2021, status: 'adopted', effective: '2023-03-15', amendments: [] },
          NEC:  { year: 2020, status: 'adopted', effective: '2023-03-15', amendments: [] },
        }
      }
    }
  },

  // Additional states with state-level data
  OR: {
    name: 'Oregon', abbr: 'OR', region: 'Pacific Northwest',
    stateNote: 'Oregon BCD adopts and enforces statewide building codes. OSSC, ORRC, OECC. Local amendments limited.',
    adopted: {
      OSSC: { year: 2021, status: 'adopted', effective: '2023-01-01', amendments: ['Oregon Structural Specialty Code: based on 2021 IBC', 'Seismic: SDC C-D-E along coast (Cascadia Subduction Zone)'] },
      IFC:  { year: 2021, status: 'adopted', effective: '2023-01-01', amendments: ['Oregon Fire Code: statewide mandatory'] },
      NEC:  { year: 2020, status: 'adopted', effective: '2022-01-01', amendments: [] },
      IECC: { year: 2021, status: 'adopted', effective: '2023-01-01', amendments: ['Oregon Energy Efficiency Specialty Code: enhanced for CZ 4C-5C'] },
    },
    cities: {
      'Portland': {
        type: 'city',
        adopted: {
          OSSC: { year: 2021, status: 'adopted', effective: '2023-01-01', amendments: ['Portland Zoning Code Title 33: use overlays affecting building code', 'Climate Emergency: 2030 all-electric requirement', 'Seismic: soft-story retrofit program ongoing'] },
          NEC:  { year: 2020, status: 'adopted', effective: '2022-01-01', amendments: [] },
          IFC:  { year: 2021, status: 'adopted', effective: '2023-01-01', amendments: [] },
          IECC: { year: 2021, status: 'adopted', effective: '2023-01-01', amendments: ['Portland reach code: all-electric new construction pathway per ADM-13.04.020'] },
        }
      }
    },
    counties: {}
  },

  VA: {
    name: 'Virginia', abbr: 'VA', region: 'Mid-Atlantic',
    stateNote: 'Virginia Uniform Statewide Building Code (USBC) is mandatory. DHCD enforces. Based on 2018 IBC with VA amendments. Local amendments are not permitted.',
    adopted: {
      IBC:  { year: 2018, status: 'adopted', effective: '2021-10-01', amendments: ['VUSBC (Virginia Uniform Statewide Building Code Part I: Construction)', 'Based on 2018 IBC', 'Seismic: SDC A-B throughout most of state; C near Richmond/DC corridor'] },
      IRC:  { year: 2018, status: 'adopted', effective: '2021-10-01', amendments: ['VUSBC Part II: Residential'] },
      NEC:  { year: 2017, status: 'adopted', effective: '2018-01-01', amendments: ['DPOR administers electrical licensing per NEC 2017'] },
      IFC:  { year: 2018, status: 'adopted', effective: '2021-10-01', amendments: ['Virginia Statewide Fire Prevention Code'] },
      IECC: { year: 2018, status: 'adopted', effective: '2021-10-01', amendments: ['VECC (Virginia Energy Conservation Code): based on IECC 2018', 'CZ 4A for northern VA; CZ 3A south'] },
    },
    cities: {},
    counties: {}
  },

  GA: {
    name: 'Georgia', abbr: 'GA', region: 'Southeast',
    stateNote: 'Georgia DCA adopts statewide mandatory codes. Local amendments allowed with DCA review.',
    adopted: {
      IBC:  { year: 2018, status: 'adopted', effective: '2020-01-01', amendments: ['Georgia State Minimum Standard Building Code: based on IBC 2018', 'Chapter 17: enhanced special inspection requirements'] },
      IRC:  { year: 2018, status: 'adopted', effective: '2020-01-01', amendments: [] },
      NEC:  { year: 2020, status: 'adopted', effective: '2021-01-01', amendments: [] },
      IFC:  { year: 2018, status: 'adopted', effective: '2020-01-01', amendments: [] },
      IECC: { year: 2015, status: 'adopted', effective: '2016-01-01', amendments: ['CZ 2A-4A: Georgia amendments'] },
    },
    cities: {
      'Atlanta': {
        type: 'city',
        adopted: {
          IBC:  { year: 2018, status: 'adopted', effective: '2020-01-01', amendments: ['Atlanta amendments: enhanced historic preservation requirements', 'Transit-oriented development zones: enhanced ADU provisions'] },
          NEC:  { year: 2020, status: 'adopted', effective: '2021-01-01', amendments: [] },
          IFC:  { year: 2018, status: 'adopted', effective: '2020-01-01', amendments: [] },
          IECC: { year: 2015, status: 'adopted', effective: '2016-01-01', amendments: ['Atlanta Better Buildings Challenge: voluntary stretch targets'] },
        }
      }
    },
    counties: {
      'Fulton County': {
        type: 'county',
        adopted: {
          IBC:  { year: 2018, status: 'adopted', effective: '2020-01-01', amendments: [] },
          NEC:  { year: 2020, status: 'adopted', effective: '2021-01-01', amendments: [] },
        }
      }
    }
  },

  MA: {
    name: 'Massachusetts', abbr: 'MA', region: 'Northeast',
    stateNote: 'Massachusetts adopts the Massachusetts State Building Code (780 CMR) statewide. Based on 2009 IBC with MA amendments – updating to 2015 IBC basis in 9th edition. BBRS administers.',
    adopted: {
      IBC:  { year: 2015, status: 'adopted', effective: '2020-01-01', amendments: ['780 CMR 9th Edition: based on 2015 IBC', 'Seismic: SDC B-C in eastern MA', 'Section 1101: MA accessibility enhanced (521 CMR)', '780 CMR Chapter 36: Stretch Energy Code available'] },
      IRC:  { year: 2015, status: 'adopted', effective: '2020-01-01', amendments: ['780 CMR Appendix AA: Two Family dwellings'] },
      NEC:  { year: 2020, status: 'adopted', effective: '2021-01-01', amendments: ['527 CMR 12.00: Massachusetts Electrical Code based on NEC 2020'] },
      IFC:  { year: 2015, status: 'adopted', effective: '2020-01-01', amendments: ['527 CMR 1.00: Massachusetts Fire Prevention Regulations'] },
      IECC: { year: 2018, status: 'adopted', effective: '2020-01-01', amendments: ['Base: 780 CMR Appendix AB Energy Code', 'Stretch Code: 780 CMR 115.AA – 20% better required in many municipalities', 'Specialized Code: enhanced (opt-in)'] },
    },
    cities: {
      'Boston': {
        type: 'city',
        adopted: {
          IBC:  { year: 2015, status: 'adopted', effective: '2020-01-01', amendments: ['Boston Zoning Code and Groundwater Conservation Overlay supplement', 'Resilience: BBP Sea Level Rise+3ft minimum FFE', 'LEED Gold required for new construction >50k sqft per IDP'] },
          NEC:  { year: 2020, status: 'adopted', effective: '2021-01-01', amendments: [] },
          IFC:  { year: 2015, status: 'adopted', effective: '2020-01-01', amendments: ['Boston Fire Prevention Code: BFD amendments'] },
          IECC: { year: 2018, status: 'adopted', effective: '2020-01-01', amendments: ['Boston Stretch Code mandatory', 'BERDO: building emissions reduction + disclosure ordinance applies >35k sqft'] },
        }
      }
    },
    counties: {}
  },

  // Quick stub states for the browser tree
  HI: { name: 'Hawaii', abbr: 'HI', region: 'Pacific', stateNote: 'State building code based on IBC 2015.', adopted: { IBC:{ year:2015,status:'adopted',effective:'2016-01-01',amendments:['Hawaii State Building Code: IBC 2015 basis','High Wind: 110-130 mph Vult throughout','Tsunami hazard zone: enhanced coastal requirements'] }, NEC:{year:2020,status:'adopted',effective:'2022-01-01',amendments:[]}, IFC:{year:2015,status:'adopted',effective:'2016-01-01',amendments:[]} }, cities:{}, counties:{} },
  ID: { name: 'Idaho', abbr: 'ID', region: 'Mountain', stateNote: 'No mandatory statewide building code. IFC adopted statewide.', adopted: { IFC:{year:2018,status:'adopted',effective:'2020-01-01',amendments:[]}, NEC:{year:2020,status:'adopted',effective:'2022-01-01',amendments:[]} }, cities:{ 'Boise':{type:'city',adopted:{ IBC:{year:2018,status:'adopted',effective:'2021-01-01',amendments:['WUI provisions for bench/foothills areas']}, NEC:{year:2020,status:'adopted',effective:'2022-01-01',amendments:[]}, IFC:{year:2018,status:'adopted',effective:'2021-01-01',amendments:[]} }} }, counties:{} },
  MN: { name: 'Minnesota', abbr: 'MN', region: 'Midwest', stateNote: 'MN DLI administers Minnesota Building Code (MBC): based on IBC 2015. Statewide mandatory.', adopted: { IBC:{year:2015,status:'adopted',effective:'2020-03-31',amendments:['MBC 2020: based on IBC 2015 with MN amendments','Chapter 1301: state amendments throughout','1341: Minnesota Accessibility Code – exceeds ADA']}, IRC:{year:2015,status:'adopted',effective:'2020-03-31',amendments:[]}, NEC:{year:2020,status:'adopted',effective:'2020-06-01',amendments:[]}, IFC:{year:2015,status:'adopted',effective:'2020-03-31',amendments:[]}, IECC:{year:2015,status:'adopted',effective:'2020-03-31',amendments:['MN Energy Code: CZ 6-7 enhanced requirements']} }, cities:{ 'Minneapolis':{type:'city',adopted:{ IBC:{year:2015,status:'adopted',effective:'2020-03-31',amendments:['Minneapolis amendments: Chapter 6 local','Green Building Policy: LEED Silver >50k sqft']}, NEC:{year:2020,status:'adopted',effective:'2020-06-01',amendments:[]}, IFC:{year:2015,status:'adopted',effective:'2020-03-31',amendments:[]} }} }, counties:{} },
  OH: { name: 'Ohio', abbr: 'OH', region: 'Midwest', stateNote: 'Ohio BBS administers Ohio Building Code (OBC) statewide. Based on IBC 2017.', adopted: { IBC:{year:2017,status:'adopted',effective:'2017-11-01',amendments:['OBC: based on IBC 2017 with Ohio amendments','Section 4101:1 OBC fire and life safety']}, NEC:{year:2017,status:'adopted',effective:'2018-01-01',amendments:[]}, IFC:{year:2017,status:'adopted',effective:'2017-11-01',amendments:[]}, IECC:{year:2017,status:'adopted',effective:'2017-11-01',amendments:[]} }, cities:{ 'Columbus':{type:'city',adopted:{ IBC:{year:2017,status:'adopted',effective:'2017-11-01',amendments:[]}, NEC:{year:2017,status:'adopted',effective:'2018-01-01',amendments:[]}, IFC:{year:2017,status:'adopted',effective:'2017-11-01',amendments:[]} }}, 'Cleveland':{type:'city',adopted:{ IBC:{year:2017,status:'adopted',effective:'2017-11-01',amendments:['Cleveland amendments: historic district provisions','Lake Erie waterfront setback requirements']}, NEC:{year:2017,status:'adopted',effective:'2018-01-01',amendments:[]} }} }, counties:{} },
  PA: { name: 'Pennsylvania', abbr: 'PA', region: 'Mid-Atlantic', stateNote: 'PA UCC (Uniform Construction Code) is mandatory statewide except for first class cities (Philadelphia). Based on IBC 2018.', adopted: { IBC:{year:2018,status:'adopted',effective:'2022-10-01',amendments:['PA UCC: 2018 IBC basis','Radon: Chapter 11 PA mandatory radon-resistant construction']}, IRC:{year:2018,status:'adopted',effective:'2022-10-01',amendments:['Radon: Appendix F mandatory']}, NEC:{year:2017,status:'adopted',effective:'2019-01-01',amendments:[]}, IFC:{year:2018,status:'adopted',effective:'2022-10-01',amendments:[]}, IECC:{year:2018,status:'adopted',effective:'2022-10-01',amendments:[]} }, cities:{ 'Philadelphia':{type:'city',adopted:{ IBC:{year:null,status:'own-code',effective:'2022-01-01',amendments:['Philadelphia Building Construction and Occupancy Code: based on IBC 2018 with PhilaCode amendments','Title 4 Philadelphia Code: local amendments throughout','Energy: Philly Energy Campaign stretch code pathway']}, NEC:{year:2017,status:'adopted',effective:'2019-01-01',amendments:[]}, IFC:{year:2018,status:'adopted',effective:'2022-01-01',amendments:['Philadelphia Fire Code: enhanced provisions']} }} }, counties:{} },
};

