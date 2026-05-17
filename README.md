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

### 2.1 Example Description

This tutorial demonstrates **Mode 2: Single Pile Stiffness** in the m-method framework of ***PileAnalysis***.

The example scenario is the same as that used in Tutorial 1. The foundation consists of two vertical circular piles arranged symmetrically along the Y direction. Both piles use the same pile type and the same soil-layer parameters.

Different from Mode 1, which calculates the **global stiffness matrix of the whole pile group foundation**, Mode 2 focuses on the stiffness of a **specified single pile**. In this tutorial, **Pile No. 2** is selected as the target pile, and the program calculates the stiffness matrix corresponding to this selected pile.

<p align="center">
  <img src="figs/example2/m_method_pile_arrangement2.png" width="80%" />
</p>

<p align="center">
  <b>Fig. 2. Selecting Pile No. 2 for single pile stiffness analysis.</b>
</p>

---

### 2.2 Calculation Workflow

The overall calculation workflow of this tutorial is basically the same as Tutorial 1. Users still need to define the pile type, pile material parameters, embedded soil-layer parameters, pile-tip parameters, and pile coordinates.

The only additional step is to specify the target pile number in the pile arrangement interface. In this example, **Pile No. 2** is selected. After the target pile is selected, the analysis can be performed directly.

For Mode 2, no external load input is required. The purpose of this mode is to obtain the equivalent stiffness of the selected pile rather than to calculate the response under a specific load case.

---

### 2.3 Visualization and Result Export

The visualization process is the same as that in Tutorial 1. After the calculation is completed, users can view the 3D layout and plan layout to check the pile position and pile numbering.

The result output and export process are also similar to Tutorial 1. The difference is that the exported stiffness matrix corresponds to **Pile No. 2**, rather than the global cap stiffness matrix of the whole pile group.

Therefore, this tutorial is not repeated in detail. Users can follow the same visualization and export procedure introduced in Tutorial 1, while noting that the result in this case represents the **single pile stiffness matrix of Pile No. 2**.

This example is also built into ***PileAnalysis***. Users can load it directly from the menu bar by selecting **Examples → Mode 2 Example: Single Pile Stiffness**.

## Tutorial 3: M-method Back-Analysis

### 3.1 Example Description

This tutorial demonstrates **Mode 3: Back Analysis** in the m-method framework of ***PileAnalysis***. The example corresponds to **Example 1 in the PILE manual case series**, and is also used as a reference example in the related paper.

Different from Mode 1 and Mode 2, which focus on stiffness calculation, Mode 3 is used to calculate the pile foundation response under specified external loads. The program can output pile-head displacement, pile-head internal forces, and response distributions along each pile, including displacement, axial force, and bending moment.

In this example, the foundation consists of **12 piles** arranged in a rectangular pile group. Two load points are applied on the pile cap. Each load point contains horizontal forces, vertical force, and bending moments. The pile group response is calculated under the simultaneous action of the two load points.

<p align="center">
  <img src="figs/example3/exanple3%20des.png" width="85%" />
</p>

<p align="center">
  <b>Fig. 1. Schematic of the PILE manual Example 1 used in this tutorial.</b>
</p>

---

### 3.2 Load Input

For Mode 3, external loads must be defined before running the analysis. This example uses **multiple loads acting simultaneously**. Two load points are applied on the pile cap, located at `(-3.0, 0.0)` and `(3.0, 0.0)`.

For each load point, the applied load components are:

| Load Point | X (m) | Y (m) | Nx (kN) | Ny (kN) | Nz (kN) | Mx (kN·m) | My (kN·m) | Mz (kN·m) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Load 1 | -3.0 | 0.0 | 50.0 | 200.0 | 8000.0 | 2000.0 | 500.0 | 0.0 |
| Load 2 | 3.0 | 0.0 | 50.0 | 200.0 | 8000.0 | 2000.0 | 500.0 | 0.0 |

<p align="center">
  <img src="figs/example3/load%20input.png" width="75%" />
</p>

<p align="center">
  <b>Fig. 2. Multiple load input for the back-analysis example.</b>
</p>

---

### 3.3 Pile Definition with Two-Section Geometry

After defining the load cases, the next step is to define the pile type and pile-soil parameters.

The main feature of this example is that each pile is defined with **two different pile diameters along the depth**. The upper section has a diameter of `1.5 m`, while the lower section has a diameter of `1.0 m`. This setting is used to model a stepped pile geometry, where the pile cross-section changes along the embedded depth.

In the pile definition interface, the above-ground segment is defined first. In this example, the free segment length is `2.0 m`, the diameter is `1.5 m`, and the subdivision count is `2`.

The embedded segment is then divided into two layers:

| Segment | Layer Thickness H (m) | Diameter D (m) | m Value (kN/m^4) | Internal Friction Angle φ | Subdivision Count N |
|---|---:|---:|---:|---:|---:|
| 1 | 10.0 | 1.5 | 1000.0 | 20.0 | 10 |
| 2 | 9.0 | 1.0 | 1000.0 | 20.0 | 9 |

The pile tip is modeled as a bored friction pile, and the pile-tip foundation coefficient is defined at the bottom of the input page.

<p align="center">
  <img src="figs/example3/pile%20definition.png" width="75%" />
</p>

<p align="center">
  <b>Fig. 3. Pile definition with two-section pile geometry.</b>
</p>

Other pile material, soil parameter, and pile arrangement operations are similar to those introduced in Tutorial 1 and are not repeated here.

---

### 3.4 Visualization and Result Interpretation

After the load input, pile definition, and pile arrangement are completed, the analysis can be performed. The program provides 3D layout, plan layout, and pile response visualization.

The 3D view shows the overall pile group and cap geometry, while the plan view shows the pile numbering, pile locations, and the applied load points.

<table>
  <tr>
    <td align="center" width="50%">
      <img src="figs/example3/3D%20view.png" width="100%" />
      <br>
      <b>Fig. 4. 3D layout of the 12-pile foundation.</b>
    </td>
    <td align="center" width="50%">
      <img src="figs/example3/plan%20view.png" width="100%" />
      <br>
      <b>Fig. 5. Plan layout and load positions.</b>
    </td>
  </tr>
</table>

The **Pile Response** tab allows users to inspect the response of each pile. For each pile, ***PileAnalysis*** can display displacement, axial force, and bending moment distributions along the pile depth.

<table>
  <tr>
    <td align="center" width="33%">
      <img src="figs/example3/displament.png" width="100%" />
      <br>
      <b>Fig. 6. Displacement distribution.</b>
    </td>
    <td align="center" width="33%">
      <img src="figs/example3/Axial%20force.png" width="100%" />
      <br>
      <b>Fig. 7. Axial force distribution.</b>
    </td>
    <td align="center" width="33%">
      <img src="figs/example3/moment.png" width="100%" />
      <br>
      <b>Fig. 8. Bending moment distribution.</b>
    </td>
  </tr>
</table>

The result summary lists the pile-head displacement and pile-head internal forces for each pile.

<p align="center">
  <img src="figs/example3/summary.png" width="75%" />
</p>

<p align="center">
  <b>Fig. 9. Summary output of the back-analysis example.</b>
</p>

---

### 3.5 CSV Result Export

For Mode 3, the exported CSV results contain more response information than the stiffness modes. The main exported tables include:

- input load information;
- cap-center displacement;
- pile-head displacement summary;
- pile-head internal force summary;
- detailed pile-head response data.

The summary CSV records the load cases, cap-center displacement, and overall analysis information. The other exported tables provide pile-level response data for subsequent comparison, post-processing, or report preparation.

<table>
  <tr>
    <td align="center" width="50%">
      <img src="figs/example3/CSV1.png" width="100%" />
      <br>
      <b>Fig. 10. Analysis summary and input load information.</b>
    </td>
    <td align="center" width="50%">
      <img src="figs/example3/CSV2.png" width="100%" />
      <br>
      <b>Fig. 11. Pile-head displacement summary.</b>
    </td>
  </tr>
  <tr>
    <td align="center" width="50%">
      <img src="figs/example3/CSV3.png" width="100%" />
      <br>
      <b>Fig. 12. Pile-head internal force summary.</b>
    </td>
    <td align="center" width="50%">
      <img src="figs/example3/CSV4.png" width="100%" />
      <br>
      <b>Fig. 13. Detailed pile-head response data.</b>
    </td>
  </tr>
</table>

Other visualization and export operations are similar to those described in Tutorial 1 and are not repeated here.

---

### 3.6 Loading This Tutorial Example

This example is built into ***PileAnalysis*** as the first PILE manual example. Users can load it directly from the menu bar by selecting:

**Examples → PILE Manual Examples → Example 1**

After the example is loaded, the program automatically fills in the load input, pile definition, pile arrangement, and soil parameters. Users can then run the analysis and inspect the results following the workflow described above.
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
