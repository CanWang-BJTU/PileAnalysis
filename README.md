# ***PileAnalysis***

## Latest Release

[Click here to download ***PileAnalysis*** V3.0](https://github.com/CanWang-BJTU/PileAnalysis/releases/tag/V3.0)

---

***PileAnalysis*** is an open-source Python-based graphical user interface (GUI) program for pile foundation analysis and pile-soil interaction simulation.

***PileAnalysis*** integrates two computational frameworks:

1. **Linear elastic m-method framework**
   - Powered by a high-performance ***Fortran*** solver.
   - Supports pile group stiffness calculation, single pile stiffness calculation, and back-analysis of pile foundation response.

2. **Nonlinear pile-soil interaction framework**
   - Built on ***OpenSeesPy***.
   - Supports nonlinear *p-y*, *t-z*, and *q-z* soil spring models.
   - Supports axial, lateral, combined loading, and pile group analyses.
   - Supports interaction with ***SectionMCPy***, allowing users to import nonlinear fiber-section data and account for pile material nonlinearity in pile foundation analysis.

***PileAnalysis*** aims to provide engineers, researchers, and students with a convenient, visual, and extensible tool for pile foundation analysis without requiring complex manual scripting.

---

## Reference

<!-- Please add the citation information of the PileAnalysis paper here. -->

---

# Tutorial

***PileAnalysis*** provides nine tutorials covering the main functions of the m-method framework, the nonlinear framework, fiber-section import, and result export. All examples mentioned in this section are built into the **Example** menu of the software. Users can load the corresponding parameters into the GUI with a single click, modify them as needed, and then run the analysis based on the predefined example cases.

Users can click the following links to jump directly to each tutorial:

1. [Tutorial 1: M-method Pile Group Stiffness Analysis](#tutorial-1-m-method-pile-group-stiffness-analysis)
2. [Tutorial 2: M-method Single Pile Stiffness Analysis](#tutorial-2-m-method-single-pile-stiffness-analysis)
3. [Tutorial 3: M-method Back-Analysis](#tutorial-3-m-method-back-analysis)
4. [Tutorial 4: Nonlinear Axially Loaded Pile Analysis](#tutorial-4-nonlinear-axially-loaded-pile-analysis)
5. [Tutorial 5: Nonlinear Laterally Loaded Pile Analysis](#tutorial-5-nonlinear-laterally-loaded-pile-analysis)
6. [Tutorial 6: Nonlinear Combined Loading Analysis](#tutorial-6-nonlinear-combined-loading-analysis)
7. [Tutorial 7: Nonlinear Pile Group Analysis](#tutorial-7-nonlinear-pile-group-analysis)
8. [Tutorial 8: Nonlinear Fiber Section Import](#tutorial-8-nonlinear-fiber-section-import)
9. [Tutorial 9: Export Module and Special Functions](#tutorial-9-export-module-and-special-functions)

---

## Tutorial 1: M-method Pile Group Stiffness Analysis

<!-- 
This tutorial introduces the pile group stiffness calculation mode in the m-method framework.

Suggested contents:
- Purpose of this mode
- Required input parameters
- Step-by-step operation
- Result visualization
- Stiffness matrix export
- Example screenshots
-->

---

## Tutorial 2: M-method Single Pile Stiffness Analysis

<!-- 
This tutorial introduces the single pile stiffness calculation mode in the m-method framework.

Suggested contents:
- Purpose of this mode
- How to select the target pile
- Required input parameters
- Step-by-step operation
- Result visualization
- Single pile stiffness matrix export
- Example screenshots
-->

---

## Tutorial 3: M-method Back-Analysis

<!-- 
This tutorial introduces the back-analysis mode in the m-method framework.

Suggested contents:
- Purpose of this mode
- Load input
- Load application point definition
- Pile definition
- Pile arrangement
- Result visualization
- Response curve export
- Example screenshots
-->

---

## Tutorial 4: Nonlinear Axially Loaded Pile Analysis

<!-- 
This tutorial introduces the axially loaded pile analysis mode in the nonlinear framework.

Suggested contents:
- Purpose of this mode
- Soil material definition
- *t-z* spring model
- *q-z* spring model
- Pile definition
- Axial load input
- Result visualization
- Spring parameter export
- Example screenshots
-->

---

## Tutorial 5: Nonlinear Laterally Loaded Pile Analysis

<!-- 
This tutorial introduces the laterally loaded pile analysis mode in the nonlinear framework.

Suggested contents:
- Purpose of this mode
- Soil material definition
- *p-y* spring model
- Pile definition
- Lateral load input
- Result visualization
- *p-y* curve output
- Example screenshots
-->

---

## Tutorial 6: Nonlinear Combined Loading Analysis

<!-- 
This tutorial introduces the combined loading analysis mode in the nonlinear framework.

Suggested contents:
- Purpose of this mode
- Axial and lateral soil spring definition
- Pile definition
- Combined load input
- Result visualization
- Response curve export
- Example screenshots
-->

---

## Tutorial 7: Nonlinear Pile Group Analysis

<!-- 
This tutorial introduces the pile group analysis mode in the nonlinear framework.

Suggested contents:
- Purpose of this mode
- Soil material definition
- Soil layer definition
- Pile definition
- Cap definition
- Pile layout
- Load input
- Result visualization
- Node and spring parameter export
- Example screenshots
-->

---

## Tutorial 8: Nonlinear Fiber Section Import

<!-- 
This tutorial introduces how to import nonlinear fiber-section data from ***SectionMCPy***.

Suggested contents:
- Purpose of fiber-section import
- ***SectionMCPy*** data preparation
- HDF5 file import
- Fiber section visualization
- Connection with nonlinear pile analysis
- Example screenshots
-->

---

## Tutorial 9: Export Module and Special Functions

<!-- 
This tutorial introduces the export module and other special functions of ***PileAnalysis***.

Suggested contents:
- Result summary export
- Response curve export
- Stiffness matrix export
- Soil spring parameter export
- Node coordinate export
- Fiber-section data export
- Batch figure export
- External finite element software interaction
- Example screenshots
-->
