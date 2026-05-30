"""
Bundled example proteins from the AlloGator paper (Kannan et al., Cell Systems).

These are the three case-study enzymes shown in Fig. 1d-f. Each ships with the
canonical UniProt sequence and the benchmark active-site labels used in the paper
(1-indexed against the sequence given here), so a user can reproduce a paper-style
run in one click.
"""

EXAMPLES = [
    {
        "id": "hk1",
        "label": "Hexokinase-1 (human, product inhibition)",
        "uniprot": "P19367",
        "pdb": "1qha",
        "active_residues": "539, 603, 657",
        "note": "Catalytic residues. ESM-1b ranks the distal G6P-contact allosteric residues (AUROC 0.83), substantially above Ohm and EVcouplings (Fig. 1d).",
        "sequence": (
            "MIAAQLLAYYFTELKDDQVKKIDKYLYAMRLSDETLIDIMTRFRKEMKNGLSRDFNPTATVKMLPTFVRS"
            "IPDGSEKGDFIALDLGGSSFRILRVQVNHEKNQNVHMESEVYDTPENIVHGSGSQLFDHVAECLGDFMEK"
            "RKIKDKKLPVGFTFSFPCQQSKIDEAILITWTKRFKASGVEGADVVKLLNKAIKKRGDYDANIVAVVNDT"
            "VGTMMTCGYDDQHCEVGLIIGTGTNACYMEELRHIDLVEGDEGRMCINTEWGAFGDDGSLEDIRTEFDRE"
            "IDRGSLNPGKQLFEKMVSGMYLGELVRLILVKMAKEGLLFEGRITPELLTRGKFNTSDVSAIEKNKEGLH"
            "NAKEILTRLGVEPSDDDCVSVQHVCTIVSFRSANLVAATLGAILNRLRDNKGTPRLRTTVGVDGSLYKTH"
            "PQYSRRFHKTLRRLVPDSDVRFLLSESGSGKGAAMVTAVAYRLAEQHRQIEETLAHFHLTKDMLLEVKKR"
            "MRAEMELGLRKQTHNNAVVKMLPSFVRRTPDGTENGDFLALDLGGTNFRVLLVKIRSGKKRTVEMHNKIY"
            "AIPIEIMQGTGEELFDHIVSCISDFLDYMGIKGPRMPLGFTFSFPCQQTSLDAGILITWTKGFKATDCVG"
            "HDVVTLLRDAIKRREEFDLDVVAVVNDTVGTMMTCAYEEPTCEVGLIVGTGSNACYMEEMKNVEMVEGDQ"
            "GQMCINMEWGAFGDNGCLDDIRTHYDRLVDEYSLNAGKQRYEKMISGMYLGEIVRNILIDFTKKGFLFRG"
            "QISETLKTRGIFETKFLSQIESDRLALLQVRAILQQLGLNSTCDDSILVKTVCGVVSRRAAQLCGAGMAA"
            "VVDKIRENRGLDRLNVTVGVDGTLYKLHPHFSRIMHQTVKELSPKCNVSFLLSEDGSGKGAALITAVGVR"
            "LRTEASS"
        ),
    },
    {
        "id": "lldh",
        "label": "L-lactate dehydrogenase (B. longum, MWC enzyme)",
        "uniprot": "E8ME30",
        "pdb": "1lth",
        "active_residues": "181",
        "note": "Catalytic His. ESM-1b cleanly recovers the FBP allosteric site (AUROC 0.93) from a single chain where MSA-based EVcouplings fails (Fig. 1e).",
        "sequence": (
            "MAETTVKPTKLAVIGAGAVGSTLAFAAAQRGIAREIVLEDIAKERVEAEVLDMQHGSSFYPTVSIDGSDD"
            "PEICRDADMVVITAGPRQKPGQSRLELVGATVNILKAIMPNLVKVAPNAIYMLITNPVDIATHVAQKLTG"
            "LPENQIFGSGTNLDSARLRFLIAQQTGVNVKNVHAYIAGEHGDSEVPLWESATIGGVPMCDWTPLPGHDP"
            "LDADKREEIHQEVKNAAYKIINGKGATNYAIGMSGVDIIEAVLHDTNRILPVSSMLKDFHGISDICMSVP"
            "TLLNRQGVNNTINTPVSDKELAALKRSAETLKETAAQFGF"
        ),
    },
    {
        "id": "pfk1",
        "label": "Phosphofructokinase-1 (E. coli, interface effector)",
        "uniprot": "P0A796",
        "pdb": "1pfk",
        "active_residues": "12, 73, 104, 126, 128, 130, 172",
        "note": "Catalytic / substrate residues. A hard multi-chain case: the effector pocket sits at a subunit interface, challenging a single-sequence model (Fig. 1f).",
        "sequence": (
            "MIKKIGVLTSGGDAPGMNAAIRGVVRSALTEGLEVMGIYDGYLGLYEDRMVQLDRYSVSDMINRGGTFLG"
            "SARFPEFRDENIRAVAIENLKKRGIDALVVIGGDGSYMGAMRLTEMGFPCIGLPGTIDNDIKGTDYTIGF"
            "FTALSTVVEAIDRLRDTSSSHQRISVVEVMGRYCGDLTLAAAIAGGCEFVVVPEVEFSREDLVNEIKAGI"
            "AKGKKHAIVAITEHMCDVDELAHFIEKETGRETRATVLGHIQRGGSPVPYDRILASRMGAYAIDLLLAGY"
            "GGRCVGIQNEQLVHHDIIDAIENMKRPFKGDWLDCAKKLY"
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
            "pdb": e["pdb"],
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
