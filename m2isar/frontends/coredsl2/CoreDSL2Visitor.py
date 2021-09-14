# Generated from CoreDSL2.g4 by ANTLR 4.9.2
from antlr4 import *
if __name__ is not None and "." in __name__:
    from .CoreDSL2Parser import CoreDSL2Parser
else:
    from CoreDSL2Parser import CoreDSL2Parser

# This class defines a complete generic visitor for a parse tree produced by CoreDSL2Parser.

class CoreDSL2Visitor(ParseTreeVisitor):

    # Visit a parse tree produced by CoreDSL2Parser#description_content.
    def visitDescription_content(self, ctx:CoreDSL2Parser.Description_contentContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#import_file.
    def visitImport_file(self, ctx:CoreDSL2Parser.Import_fileContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#isa.
    def visitIsa(self, ctx:CoreDSL2Parser.IsaContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#instruction_set.
    def visitInstruction_set(self, ctx:CoreDSL2Parser.Instruction_setContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#core_def.
    def visitCore_def(self, ctx:CoreDSL2Parser.Core_defContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#section_arch_state.
    def visitSection_arch_state(self, ctx:CoreDSL2Parser.Section_arch_stateContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#decl_or_expr.
    def visitDecl_or_expr(self, ctx:CoreDSL2Parser.Decl_or_exprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#section_functions.
    def visitSection_functions(self, ctx:CoreDSL2Parser.Section_functionsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#section_instructions.
    def visitSection_instructions(self, ctx:CoreDSL2Parser.Section_instructionsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#instruction.
    def visitInstruction(self, ctx:CoreDSL2Parser.InstructionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#encoding.
    def visitEncoding(self, ctx:CoreDSL2Parser.EncodingContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#field.
    def visitField(self, ctx:CoreDSL2Parser.FieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#bit_value.
    def visitBit_value(self, ctx:CoreDSL2Parser.Bit_valueContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#bit_field.
    def visitBit_field(self, ctx:CoreDSL2Parser.Bit_fieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#function_definition.
    def visitFunction_definition(self, ctx:CoreDSL2Parser.Function_definitionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#parameter_list.
    def visitParameter_list(self, ctx:CoreDSL2Parser.Parameter_listContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#parameter_declaration.
    def visitParameter_declaration(self, ctx:CoreDSL2Parser.Parameter_declarationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#statement.
    def visitStatement(self, ctx:CoreDSL2Parser.StatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#labeled_statement.
    def visitLabeled_statement(self, ctx:CoreDSL2Parser.Labeled_statementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#compound_statement.
    def visitCompound_statement(self, ctx:CoreDSL2Parser.Compound_statementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#block_item.
    def visitBlock_item(self, ctx:CoreDSL2Parser.Block_itemContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#expression_statement.
    def visitExpression_statement(self, ctx:CoreDSL2Parser.Expression_statementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#selection_statement.
    def visitSelection_statement(self, ctx:CoreDSL2Parser.Selection_statementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#if_statement.
    def visitIf_statement(self, ctx:CoreDSL2Parser.If_statementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#switch_statement.
    def visitSwitch_statement(self, ctx:CoreDSL2Parser.Switch_statementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#iteration_statement.
    def visitIteration_statement(self, ctx:CoreDSL2Parser.Iteration_statementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#for_condition.
    def visitFor_condition(self, ctx:CoreDSL2Parser.For_conditionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#jump_statement.
    def visitJump_statement(self, ctx:CoreDSL2Parser.Jump_statementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#spawn_statement.
    def visitSpawn_statement(self, ctx:CoreDSL2Parser.Spawn_statementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#declaration.
    def visitDeclaration(self, ctx:CoreDSL2Parser.DeclarationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#declarationSpecifier.
    def visitDeclarationSpecifier(self, ctx:CoreDSL2Parser.DeclarationSpecifierContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#attribute.
    def visitAttribute(self, ctx:CoreDSL2Parser.AttributeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#type_specifier.
    def visitType_specifier(self, ctx:CoreDSL2Parser.Type_specifierContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#primitive_type.
    def visitPrimitive_type(self, ctx:CoreDSL2Parser.Primitive_typeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#bit_size_specifier.
    def visitBit_size_specifier(self, ctx:CoreDSL2Parser.Bit_size_specifierContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#enum_type.
    def visitEnum_type(self, ctx:CoreDSL2Parser.Enum_typeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#enumerator_list.
    def visitEnumerator_list(self, ctx:CoreDSL2Parser.Enumerator_listContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#enumerator.
    def visitEnumerator(self, ctx:CoreDSL2Parser.EnumeratorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#composite_type.
    def visitComposite_type(self, ctx:CoreDSL2Parser.Composite_typeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#struct_declaration.
    def visitStruct_declaration(self, ctx:CoreDSL2Parser.Struct_declarationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#struct_declarationSpecifier.
    def visitStruct_declarationSpecifier(self, ctx:CoreDSL2Parser.Struct_declarationSpecifierContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#init_declarator.
    def visitInit_declarator(self, ctx:CoreDSL2Parser.Init_declaratorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#direct_declarator.
    def visitDirect_declarator(self, ctx:CoreDSL2Parser.Direct_declaratorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#initializer.
    def visitInitializer(self, ctx:CoreDSL2Parser.InitializerContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#initializerList.
    def visitInitializerList(self, ctx:CoreDSL2Parser.InitializerListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#designated_initializer.
    def visitDesignated_initializer(self, ctx:CoreDSL2Parser.Designated_initializerContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#designator.
    def visitDesignator(self, ctx:CoreDSL2Parser.DesignatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#abstract_declarator.
    def visitAbstract_declarator(self, ctx:CoreDSL2Parser.Abstract_declaratorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#direct_abstract_declarator.
    def visitDirect_abstract_declarator(self, ctx:CoreDSL2Parser.Direct_abstract_declaratorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#expression_list.
    def visitExpression_list(self, ctx:CoreDSL2Parser.Expression_listContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#assignment_expression.
    def visitAssignment_expression(self, ctx:CoreDSL2Parser.Assignment_expressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#assignment.
    def visitAssignment(self, ctx:CoreDSL2Parser.AssignmentContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#conditional_expression.
    def visitConditional_expression(self, ctx:CoreDSL2Parser.Conditional_expressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#concatenation_expression.
    def visitConcatenation_expression(self, ctx:CoreDSL2Parser.Concatenation_expressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#logical_or_expression.
    def visitLogical_or_expression(self, ctx:CoreDSL2Parser.Logical_or_expressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#logical_and_expression.
    def visitLogical_and_expression(self, ctx:CoreDSL2Parser.Logical_and_expressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#inclusive_or_expression.
    def visitInclusive_or_expression(self, ctx:CoreDSL2Parser.Inclusive_or_expressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#exclusive_or_expression.
    def visitExclusive_or_expression(self, ctx:CoreDSL2Parser.Exclusive_or_expressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#and_expression.
    def visitAnd_expression(self, ctx:CoreDSL2Parser.And_expressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#equality_expression.
    def visitEquality_expression(self, ctx:CoreDSL2Parser.Equality_expressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#relational_expression.
    def visitRelational_expression(self, ctx:CoreDSL2Parser.Relational_expressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#shift_expression.
    def visitShift_expression(self, ctx:CoreDSL2Parser.Shift_expressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#additive_expression.
    def visitAdditive_expression(self, ctx:CoreDSL2Parser.Additive_expressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#multiplicative_expression.
    def visitMultiplicative_expression(self, ctx:CoreDSL2Parser.Multiplicative_expressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#cast_expression.
    def visitCast_expression(self, ctx:CoreDSL2Parser.Cast_expressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#prefix_expression.
    def visitPrefix_expression(self, ctx:CoreDSL2Parser.Prefix_expressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#unary_operator.
    def visitUnary_operator(self, ctx:CoreDSL2Parser.Unary_operatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#postfix_expression.
    def visitPostfix_expression(self, ctx:CoreDSL2Parser.Postfix_expressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#postfix.
    def visitPostfix(self, ctx:CoreDSL2Parser.PostfixContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#primary_expression.
    def visitPrimary_expression(self, ctx:CoreDSL2Parser.Primary_expressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#string_literal.
    def visitString_literal(self, ctx:CoreDSL2Parser.String_literalContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#constant_expression.
    def visitConstant_expression(self, ctx:CoreDSL2Parser.Constant_expressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#constant.
    def visitConstant(self, ctx:CoreDSL2Parser.ConstantContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#integer_constant.
    def visitInteger_constant(self, ctx:CoreDSL2Parser.Integer_constantContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#floating_constant.
    def visitFloating_constant(self, ctx:CoreDSL2Parser.Floating_constantContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#bool_constant.
    def visitBool_constant(self, ctx:CoreDSL2Parser.Bool_constantContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#character_constant.
    def visitCharacter_constant(self, ctx:CoreDSL2Parser.Character_constantContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#double_left_bracket.
    def visitDouble_left_bracket(self, ctx:CoreDSL2Parser.Double_left_bracketContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#double_right_bracket.
    def visitDouble_right_bracket(self, ctx:CoreDSL2Parser.Double_right_bracketContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#data_types.
    def visitData_types(self, ctx:CoreDSL2Parser.Data_typesContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#type_qualifier.
    def visitType_qualifier(self, ctx:CoreDSL2Parser.Type_qualifierContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#storage_class_specifier.
    def visitStorage_class_specifier(self, ctx:CoreDSL2Parser.Storage_class_specifierContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#attributeName.
    def visitAttributeName(self, ctx:CoreDSL2Parser.AttributeNameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CoreDSL2Parser#struct_or_union.
    def visitStruct_or_union(self, ctx:CoreDSL2Parser.Struct_or_unionContext):
        return self.visitChildren(ctx)



del CoreDSL2Parser