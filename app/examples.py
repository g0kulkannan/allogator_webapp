"""
Bundled example proteins from the AlloGator paper (Kannan et al., Cell Systems).

Each example ships with the canonical UniProt sequence and its annotated
catalytic active-site residues, so a user can reproduce a paper-style run
in one click. Active-site numbering is 1-indexed against the sequence given
here (the full UniProt canonical sequence).
"""

EXAMPLES = [
    {
        "id": "dpp4",
        "label": "DPP4 (human protease)",
        "uniprot": "P27487",
        "active_residues": "630, 708, 740",
        "note": "Catalytic triad. The paper used language-model attention to "
                "discover the allosteric residues T736 and S744 in DPP4.",
        "sequence": (
            "MKTPWKVLLGLLGAAALVTIITVPVVLLNKGTDDATADSRKTYTLTDYLKNTYRLKLYSLRWISDHEYLYKQ"
            "ENNILVFNAEYGNSSVFLENSTFDEFGHSINDYSISPDGQFILLEYNYVKQWRHSYTASYDIYDLNKRQLIT"
            "EERIPNNTQWVTWSPVGHKLAYVWNNDIYVKIEPNLPSYRITWTGKEDIIYNGITDWVYEEEVFSAYSALWW"
            "SPNGTFLAYAQFNDTEVPLIEYSFYSDESLQYPKTVRVPYPKAGAVNPTVKFFVVNTDSLSSVTNATSIQIT"
            "APASMLIGDHYLCDVTWATQERISLQWLRRIQNYSVMDICDYDESSGRWNCLVARQHIEMSTTGWVGRFRPS"
            "EPHFTLDGNSFYKIISNEEGYRHICYFQIDKKDCTFITKGTWEVIGIEALTSDYLYYISNEYKGMPGGRNLY"
            "KIQLSDYTKVTCLSCELNPERCQYYSVSFSKEAKYYQLRCSGPGLPLYTLHSSVNDKGLRVLEDNSALDKML"
            "QNVQMPSKKLDFIILNETKFWYQMILPPHFDKSKKYPLLLDVYAGPCSQKADTVFRLNWATYLASTENIIVA"
            "SFDGRGSGYQGDKIMHAINRRLGTFEVEDQIEAARQFSKMGFVDNKRIAIWGWSYGGYVTSMVLGSGSGVFK"
            "CGIAVAPVSRWEYYDSVYTERYMGLPTPEDNLDHYRNSTVMSRAENFKQVEYLLIHGTADDNVHFQQSAQIS"
            "KALVDVGVDFQAMWYTDEDHGIASSTAHQHIYTHMSHFIKQCFSLP"
        ),
    },
    {
        "id": "ace2",
        "label": "ACE2 (chloride-activated carboxypeptidase)",
        "uniprot": "Q9BYF1",
        "active_residues": "375, 505",
        "note": "Catalytic residues. The paper identified R393, L391 and M366 "
                "as residues coupled to the known chloride allosteric pathway.",
        "sequence": (
            "MSSSSWLLLSLVAVTAAQSTIEEQAKTFLDKFNHEAEDLFYQSSLASWNYNTNITEENVQNMNNAGDKWSAF"
            "LKEQSTLAQMYPLQEIQNLTVKLQLQALQQNGSSVLSEDKSKRLNTILNTMSTIYSTGKVCNPDNPQECLLL"
            "EPGLNEIMANSLDYNERLWAWESWRSEVGKQLRPLYEEYVVLKNEMARANHYEDYGDYWRGDYEVNGVDGYD"
            "YSRGQLIEDVEHTFEEIKPLYEHLHAYVRAKLMNAYPSYISPIGCLPAHLLGDMWGRFWTNLYSLTVPFGQK"
            "PNIDVTDAMVDQAWDAQRIFKEAEKFFVSVGLPNMTQGFWENSMLTDPGNVQKAVCHPTAWDLGKGDFRILM"
            "CTKVTMDDFLTAHHEMGHIQYDMAYAAQPFLLRNGANEGFHEAVGEIMSLSAATPKHLKSIGLLSPDFQEDN"
            "ETEINFLLKQALTIVGTLPFTYMLEKWRWMVFKGEIPKDQWMKKWWEMKREIVGVVEPVPHDETYCDPASLF"
            "HVSNDYSFIRYYTRTLYQFQFQEALCQAAKHEGPLHKCDISNSTEAGQKLFNMLRLGKSEPWTLALENVVGA"
            "KNMNVRPLLNYFEPLFTWLKDQNKNSFVGWSTDWSPYADQSIKVRISLKSALGDKAYEWNDNEMYLFRSSVA"
            "YAMRQYFLKVKNQMILFGEEDVRVANLKPRISFNFFVTAPKNVSDIIPRTEVEKAIRMSRSRINDAFRLNDN"
            "SLEFLGIQPTLGPPNQPPVSIWLIVFGVVMGVIVVGIVILIFTGIRDRKKKNKARSGENPYASIDISKGENN"
            "PGFQNTDDVQTSF"
        ),
    },
    {
        "id": "lldh",
        "label": "L-lactate dehydrogenase (B. longum, MWC enzyme)",
        "uniprot": "E8ME30",
        "active_residues": "181",
        "note": "Catalytic His. A low-homology case where ESM-1b cleanly "
                "recovered the FBP allosteric site (AUROC 0.93) while "
                "MSA-based EVcouplings failed.",
        "sequence": (
            "MAETTVKPTKLAVIGAGAVGSTLAFAAAQRGIAREIVLEDIAKERVEAEVLDMQHGSSFYPTVSIDGSDDPE"
            "ICRDADMVVITAGPRQKPGQSRLELVGATVNILKAIMPNLVKVAPNAIYMLITNPVDIATHVAQKLTGLPEN"
            "QIFGSGTNLDSARLRFLIAQQTGVNVKNVHAYIAGEHGDSEVPLWESATIGGVPMCDWTPLPGHDPLDADKR"
            "EEIHQEVKNAAYKIINGKGATNYAIGMSGVDIIEAVLHDTNRILPVSSMLKDFHGISDICMSVPTLLNRQGV"
            "NNTINTPVSDKELAALKRSAETLKETAAQFGF"
        ),
    },
]


def list_examples() -> list:
    """Public example list (omits the full sequence to keep the payload small)."""
    return [
        {
            "id": e["id"],
            "label": e["label"],
            "uniprot": e["uniprot"],
            "active_residues": e["active_residues"],
            "note": e["note"],
            "length": len(e["sequence"]),
        }
        for e in EXAMPLES
    ]


def get_example(example_id: str) -> dict:
    for e in EXAMPLES:
        if e["id"] == example_id:
            return e
    raise KeyError(example_id)
