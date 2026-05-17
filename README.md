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

### 1.1 Interface Overview

This tutorial introduces the group pile stiffness calculation mode in the m-method framework of ***PileAnalysis***.

Before presenting the detailed operation procedure, the main interface of the m-method framework is briefly introduced. As shown in Fig. 1, the main interface consists of five main areas: the **menu bar**, **status bar**, **parameter input area**, **visualization area**, and **result output area**.

- **Menu Bar**  
  The menu bar provides access to the main functions of the program, including example loading, help documentation, result export, navigation, and language switching.

- **Status Bar**  
  The status bar displays the current program status, version information, author information, and operation prompts.

- **Parameter Input Area**  
  The parameter input area is used to select the analysis mode, define pile and soil parameters, configure pile arrangement, and control the analysis process.

- **Visualization Area**  
  The visualization area is used to display the analysis schematic, 3D pile layout, plan layout, and other graphical results after calculation.

- **Result Output Area**  
  The result output area displays the analysis results, including the result summary and the original solver output.

<p align="center">
  <img src="figs/example1/m_method_interface.png" width="95%" />
</p>

<p align="center">
  <b>Fig. 1. Main interface of the m-method framework.</b>
</p>

### 1.2 Example Description

This tutorial demonstrates **Mode 1: Group Pile Stiffness** in the m-method framework of ***PileAnalysis***.

In practical foundation design, a pile group is often simplified as an equivalent elastic support when it is connected to the upper structure through a pile cap. In this situation, the key output required by structural engineers is not the response under one specific load case, but the **overall stiffness relationship** between the generalized force vector and the generalized displacement vector at the pile cap reference point.

Mode 1 is designed for this purpose. It calculates the **global 6 × 6 stiffness matrix of the pile group foundation**, including translational and rotational stiffness components. The exported stiffness matrix can be used in subsequent structural analysis or finite element modeling.

The example used in this tutorial is a simple two-pile foundation. The two piles are vertical circular piles arranged symmetrically along the Y direction. Both piles use the same pile type, and no simulated pile is included. This example is intentionally simple, so users can focus on understanding the basic input logic and output interpretation of Mode 1.

In ***PileAnalysis***, a **simulated pile** is an equivalent stiffness element used to represent additional restraint effects in the pile group system. It does not behave as a real physical pile for internal-force output, but contributes stiffness to the global foundation system. This function can be used when users need to consider the influence of existing piles, auxiliary supports, cap-soil resistance, or other simplified boundary restraints.

**P.S.** A simulated-pile example is also provided in the built-in PILE manual examples. Users can load it from the menu bar by selecting **Examples → PILE Manual Examples → Example 2**.

---

### 1.3 Pile Definition

The first step is to define the pile type and the corresponding pile-soil interaction parameters.

In this example, only one pile type is used. The pile is defined as a circular vertical pile. The pile tip is treated as an end-bearing pile with a socketed tip condition. The pile direction cosines are set to indicate a vertical pile axis.

The pile material parameters include the elastic modulus and the inertia correction factor. The embedded pile segment is divided into several soil layers. For each layer, users need to define the layer thickness, pile diameter, soil m value, internal friction angle, and subdivision count. The pile-tip foundation coefficient is also defined at the bottom of the input area.

<p align="center">
  <img src="figs/example1/m_method_pile_definition.png" width="80%" />
</p>

<p align="center">
  <b>Fig. 2. Pile definition and soil layer parameters for Mode 1.</b>
</p>

During parameter input, ***PileAnalysis*** provides help buttons at the corresponding positions. These help buttons allow users to quickly check the meaning, variable name, unit, and typical range of the current parameter without leaving the input interface.

<p align="center">
  <img src="figs/example1/help button.png" width="75%" />
</p>

<p align="center">
  <b>Fig. 3. Parameter help window for pile segment definition.</b>
</p>

In addition to the local help buttons, the program also provides a summarized parameter reference window. This window collects commonly used reference information, such as recommended soil m values, rock c0 values, internal friction angle references, concrete parameters, and pile-tip constraint notes.

<p align="center">
  <img src="figs/example1/help summary.png" width="80%" />
</p>

<p align="center">
  <b>Fig. 4. Summary reference table for m-method parameters.</b>
</p>

---

### 1.4 Pile Arrangement

After defining the pile type, the next step is to assign pile positions and pile types.

In this example, the foundation contains two piles. Both piles are assigned to the same pile type. Their coordinates are arranged symmetrically along the Y direction:

| Pile No. | X Coordinate (m) | Y Coordinate (m) | Pile Type |
|---|---:|---:|---|
| 1 | 0.000 | 2.250 | type1 |
| 2 | 0.000 | -2.250 | type1 |

The simulated pile option is not enabled in this example. Therefore, the calculated stiffness matrix is contributed only by the two physical piles.

<p align="center">
  <img src="figs/example1/m_method_pile_arrangement.png" width="80%" />
</p>

<p align="center">
  <b>Fig. 5. Pile layout and pile type assignment.</b>
</p>

---

### 1.5 Analysis and Layout Visualization

After the pile definition and pile arrangement are completed, the analysis can be performed. For Mode 1, no external load input is required, because the objective is to calculate the equivalent stiffness of the pile group rather than the response under a specific load case.

After the calculation is completed, the visualization area displays the pile group layout. The 3D view shows the spatial relationship between the pile cap, the piles, and the global coordinate system. This view helps users confirm whether the pile orientation and overall arrangement are consistent with the intended model.

<p align="center">
  <img src="figs/example1/example1_3d_layout.png" width="80%" />
</p>

<p align="center">
  <b>Fig. 6. 3D layout of the two-pile foundation.</b>
</p>

The plan layout shows the pile locations in the X-Y plane. This view is useful for checking pile spacing, pile numbering, and whether the coordinates have been entered correctly.

<p align="center">
  <img src="figs/example1/example1_plan_layout.png" width="80%" />
</p>

<p align="center">
  <b>Fig. 7. Plan layout of the two-pile foundation.</b>
</p>

---

### 1.6 Result Interpretation

The main result of Mode 1 is the **Global Cap Stiffness Matrix**. This matrix represents the relationship between the generalized force components and generalized displacement components at the pile cap reference point.

The summary output reports the current analysis mode and displays the stiffness matrix result. For easier interpretation and subsequent use, the program provides both the original solver-coordinate matrix and the converted matrix using the Z-axis-upward convention.

<p align="center">
  <img src="figs/example1/example1_summary.png" width="80%" />
</p>

<p align="center">
  <b>Fig. 8. Summary output of the group pile stiffness analysis.</b>
</p>

The stiffness matrix includes translational stiffness terms related to X, Y, and Z displacement, as well as rotational stiffness terms related to rotation about the X, Y, and Z axes. Coupling terms may also appear when the pile group layout or boundary conditions produce force-displacement coupling.

---

### 1.7 Stiffness Matrix Export

The global cap stiffness matrix can be exported as a CSV file for subsequent analysis. The exported file contains the case information, unit convention, converted stiffness matrix, and original stiffness matrix.

<p align="center">
  <img src="figs/example1/export_button.png" width="55%" />
</p>

<p align="center">
  <b>Fig. 9. Stiffness matrix export menu.</b>
</p>

The exported stiffness matrix can be opened in spreadsheet software or imported into external structural analysis programs. In this example, the exported matrix records that the model contains two piles and uses kN, m, and rad as the force, length, and rotation units.

<p align="center">
  <img src="figs/example1/stiffness_matrix.png" width="75%" />
</p>

<p align="center">
  <b>Fig. 10. Exported global cap stiffness matrix.</b>
</p>

---

### 1.8 Loading This Tutorial Example

The example shown in this tutorial is built into ***PileAnalysis***. Users can load it directly from the menu bar by selecting:

**Examples → Mode 1 Example: Group Pile Stiffness**

After the example is loaded, the program automatically fills in the pile definition, pile arrangement, and soil parameters. Users can then inspect the model, modify the parameters if needed, and run the analysis following the workflow described above.

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
