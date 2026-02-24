// Fill in the rest of states with minimal data for browsing
const ALL_STATES = [
  {abbr:'AR',name:'Arkansas'},{abbr:'CT',name:'Connecticut'},{abbr:'DE',name:'Delaware'},{abbr:'IA',name:'Iowa'},
  {abbr:'IN',name:'Indiana'},{abbr:'KS',name:'Kansas'},{abbr:'KY',name:'Kentucky'},{abbr:'LA',name:'Louisiana'},
  {abbr:'ME',name:'Maine'},{abbr:'MD',name:'Maryland'},{abbr:'MI',name:'Michigan'},{abbr:'MS',name:'Mississippi'},
  {abbr:'MO',name:'Missouri'},{abbr:'MT',name:'Montana'},{abbr:'NE',name:'Nebraska'},{abbr:'NV',name:'Nevada'},
  {abbr:'NH',name:'New Hampshire'},{abbr:'NJ',name:'New Jersey'},{abbr:'NM',name:'New Mexico'},
  {abbr:'NC',name:'North Carolina'},{abbr:'ND',name:'North Dakota'},{abbr:'OK',name:'Oklahoma'},
  {abbr:'RI',name:'Rhode Island'},{abbr:'SC',name:'South Carolina'},{abbr:'SD',name:'South Dakota'},
  {abbr:'TN',name:'Tennessee'},{abbr:'UT',name:'Utah'},{abbr:'VT',name:'Vermont'},{abbr:'WV',name:'West Virginia'},
  {abbr:'WI',name:'Wisconsin'},{abbr:'WY',name:'Wyoming'}
];

ALL_STATES.forEach(s => {
  if (!JURISDICTIONS[s.abbr]) {
    JURISDICTIONS[s.abbr] = {
      name: s.name, abbr: s.abbr, region: '—',
      stateNote: 'Contact your local building department for current adopted codes. Data pending detailed research.',
      adopted: {
        IBC:  { year: 2018, status: 'adopted', effective: 'Varies', amendments: ['Contact local AHJ for specific amendments'] },
        NEC:  { year: 2020, status: 'adopted', effective: 'Varies', amendments: [] },
      },
      cities: {}, counties: {}
    };
  }
});
