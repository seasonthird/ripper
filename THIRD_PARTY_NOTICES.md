# Third-party notices

The root MIT license covers Ripper-authored additions. Incorporated components
retain their original copyright and license notices. This project does not
claim authorship of the upstream work or endorsement by its authors.

| Component | Upstream | Existing copyright notice | License |
|---|---|---|---|
| Collector lineage | [earino/resumasher](https://github.com/earino/resumasher) | Eduardo Ariño de la Rubia and contributors, 2026 | [MIT](ripper-collector/LICENSE) |
| Evidence Modeler lineage | [oxygen914/project-resume-writer](https://github.com/oxygen914/project-resume-writer) | didi, 2026 | [MIT](ripper-evidence-modeler/LICENSE) |
| CV lineage | [deusyu/claude-resume](https://github.com/deusyu/claude-resume) | deusyu, 2025 | [MIT](ripper-cv/LICENSE) |
| CV template reference | [billryan/resume](https://github.com/billryan/resume) | The CV upstream README credits this template lineage | [MIT](ripper-cv/skills/ripper-cv/assets/RESUME-TEMPLATE-LICENSE) |
| Bundled DejaVu fonts | [DejaVu Fonts](https://github.com/dejavu-fonts/dejavu-fonts) | Bitstream and other notices in the font license | [Font license](ripper-collector/assets/DejaVu-LICENSE.txt) |

Upstream identifiers were recovered from the local provenance snapshots and
existing license files. The local `zip_backup/` directory preserves historical
snapshots; it is excluded from source releases. Package dependencies retain
their respective licenses and are installed separately rather than vendored.

Keep this notice and component licenses when distributing the bundle.
