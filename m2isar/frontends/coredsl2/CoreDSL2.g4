grammar CoreDSL2;

description_content
	: imports+=import_file* definitions+=isa+
	;

import_file
	: 'import' uri=RULE_STRING
	;

isa
	: instruction_set
	| core_def
	;

instruction_set
	: 'InstructionSet' name=IDENTIFIER ('extends' extension=IDENTIFIER)? '{' sections+ '}'
	;

core_def
	: 'Core' name=IDENTIFIER ('provides' contributing_types+=IDENTIFIER (',' contributing_types+=IDENTIFIER)*)? '{' sections* '}'
	;

sections
	: section_arch_state
	| section_functions
	| section_instructions
	;

section_arch_state
	: 'architectural_state' '{' declarations+=decl_or_expr+ '}'
	;

decl_or_expr
	: declaration
	| expression ';'
	;

section_functions
	: 'functions' '{' functions+=function_definition+ '}'
	;

section_instructions
	: 'instructions' attributes+=attribute* '{' instructions+=instruction+ '}'
	;

instruction
	: name=IDENTIFIER attributes+=attribute* '{'
	'encoding' ':' encoding=rule_encoding';'
	('args_disass' ':' disass=RULE_STRING ';')?
	'behavior' ':' behavior=statement
	'}'
	;

rule_encoding
	: fields+=field ('::' fields+=field)*
	;

field
	: bit_value
	| bit_field
	;

bit_value
	: value=RULE_INTEGER
	;

bit_field
	: name=IDENTIFIER RULE_LEFT_BR left=integer_constant ':' right=integer_constant RULE_RIGHT_BR
	;

function_definition
	: 'extern' type_=type_specifier name=IDENTIFIER '(' parameter_list? ')' ';' # extern_function_definition
	| type_=type_specifier name=IDENTIFIER '(' parameter_list? ')' attributes+=attribute* behavior=block # intern_function_definition
	;

parameter_list
	: params+=parameter_declaration (',' params+=parameter_declaration)*
	;

parameter_declaration
	: type_=type_specifier declarator=direct_or_abstract_declarator?
	;

direct_or_abstract_declarator
	: direct_declarator
	| abstract_declarator
	;

statement
	: block
	| type_='if' '(' cond=expression ')' then_stmt=statement ('else' else_stmt=statement)?
	| type_='for' '(' for_condition ')' stmt=statement
	| type_='while' '(' cond=expression ')' stmt=statement
	| type_='do' stmt=statement 'while' '(' cond=expression ')' ';'
	| type_='switch' '(' cond=expression ')' '{' items+=switch_block_statement_group* switch_label* '}'
	| type_='return' expr=expression? ';'
	| type_='break' ';'
	| type_='continue' ';'
	| type_='spawn' stmt=statement
	| expr=expression ';'
	;

switch_block_statement_group
	: labels+=switch_label+ statements+=statement+
	;

switch_label
	: 'case' const_expr=expression ':'
	| 'default' ':'
	;


block
	: '{' items+=block_item* '}'
	;

block_item
	: statement
	| declaration
	;

// Rule ExpressionStatement
expression_statement: expr=expression_list? ';';

// Rule ForCondition
for_condition: (start_decl=declaration | start_expr=expression? ';') end_expr=expression? ';' (loop_exprs+=expression (',' loop_exprs+=expression)*)?;

// Rule JumpStatement
jump_statement:
	type_='continue' ';'
	| type_='break' ';'
	| type_='return' expr=expression? ';'
;

// Rule SpawnStatement
spawn_statement: 'spawn' stmt=statement;

// Rule Declaration
declaration: (storage+=storage_class_specifier | qualifiers+=type_qualifier | attributes+=attribute)* type_=type_specifier ptr=('*' | '&')? (init+=init_declarator (',' init+=init_declarator)*)? ';';

// Rule DeclarationSpecifier
declarationSpecifier: storage_class_specifier | type_qualifier | attribute;

// Rule Attribute
attribute: double_left_bracket type_=attribute_name ('=' value=expression)? double_right_bracket;

// Rule TypeSpecifier
type_specifier: primitive_type | composite_type | enum_type;

// Rule PrimitiveType
primitive_type: data_type=data_types+ bit_size=bit_size_specifier?;

// Rule BitSizeSpecifier
bit_size_specifier: '<' size+=primary_expression (',' size+=primary_expression ',' size+=primary_expression ',' size+=primary_expression)? '>';

// Rule EnumType
enum_type:
	'enum' name=IDENTIFIER? '{' enumerator_list ','? '}'
	| 'enum' name=IDENTIFIER
;

// Rule EnumeratorList
enumerator_list: enumerators+=enumerator (',' enumerators+=enumerator)*;

// Rule Enumerator
enumerator:
	name=IDENTIFIER
	| name=IDENTIFIER '=' expression
;

// Rule CompositeType
composite_type:
	type_=struct_or_union name=IDENTIFIER? '{' declarations+=struct_declaration* '}'
	| type_=struct_or_union name=IDENTIFIER
;

// Rule StructDeclaration
struct_declaration: specifier=struct_declaration_specifier declarators+=direct_declarator(',' declarators+=direct_declarator)* ';';

// Rule StructDeclarationSpecifier
struct_declaration_specifier: type_=type_specifier | qualifiers+=type_qualifier;

// Rule InitDeclarator
init_declarator: declarator=direct_declarator attributes=attribute* ('=' init=initializer)?;

// Rule DirectDeclarator
direct_declarator:
	name=IDENTIFIER (':' index=integer_constant)?
		((RULE_LEFT_BR size+=expression RULE_RIGHT_BR)+
		| '(' parameter_list ')')?
;

// Rule Initializer
initializer:
	expr=expression
	| '{' initializerList ','? '}'
;

// Rule InitializerList
initializerList: init+=designated_or_not (',' init+=designated_or_not)*;
designated_or_not: designated_initializer | initializer;

// Rule DesignatedInitializer
designated_initializer: designators+=designator+ '=' init=initializer;

// Rule Designator
designator: RULE_LEFT_BR idx=expression RULE_RIGHT_BR | '.' prop=IDENTIFIER;

// Rule AbstractDeclarator
abstract_declarator: direct_abstract_declarator;

// Rule DirectAbstractDeclarator
direct_abstract_declarator:
	'(' (decl=abstract_declarator? | parameter_list) ')'
	| RULE_LEFT_BR expr=expression? RULE_RIGHT_BR
;

// Rule ExpressionList
expression_list: expressions+=expression (',' expressions+=expression)*;

expression
	: primary_expression #primary
	| bop=('.' | '->') ref=IDENTIFIER #deref_expression
	| expression bop='[' expression (':' expression)? ']' #slice_expression
	| ref=IDENTIFIER '(' (args+=expression (',' args+=expression)*)? ')' 		#method_call
	| expression postfix=('++' | '--') #postfix_expression
    | prefix=('&'|'*'|'+'|'-'|'++'|'--') expression #prefix_expression
    | prefix=('~'|'!') expression #prefix_expression
	| '('type_=type_specifier ')' expression 								#cast_expression
    | expression bop=('*'|'/'|'%') expression #binary_expression
    | expression bop=('+'|'-') expression #binary_expression
    | expression bop=('<<' | '>>') expression #binary_expression
    | expression bop=('<=' | '>=' | '>' | '<') expression #binary_expression
    | expression bop=('==' | '!=') expression #binary_expression
    | expression bop='&' expression #binary_expression
    | expression bop='^' expression #binary_expression
    | expression bop='|' expression #binary_expression
    | expression bop='&&' expression #binary_expression
    | expression bop='||' expression #binary_expression
	| expression bop='::' expression #binary_expression
    | <assoc=right> expression bop='?' expression ':' expression #conditional_expression
	| <assoc=right> expression bop=('=' | '+=' | '-=' | '*=' | '/=' | '&=' | '|=' | '^=' | '>>=' | '>>>=' | '<<=' | '%=') expression #assignment_expression
	;


// Rule PrimaryExpression
primary_expression:
	ref=IDENTIFIER
	| const_expr=constant
	| literal+=string_literal+
	| '(' expression ')'
;

// Rule StringLiteral
string_literal: RULE_ENCSTRINGCONST | RULE_STRING;

// Rule Constant
constant:
	integer_constant
	| floating_constant
	| character_constant
	| bool_constant
;

// Rule IntegerConstant
integer_constant:
	value=RULE_INTEGER
;

// Rule FloatingConstant
floating_constant:
	value=RULE_FLOAT
;

// Rule BoolConstant
bool_constant:
	value=RULE_BOOLEAN
;

// Rule CharacterConstant
character_constant:
	value=RULE_CHARCONST
;

// Rule DoubleLeftBracket
double_left_bracket:
	RULE_LEFT_BR
	RULE_LEFT_BR
;

// Rule DoubleRightBracket
double_right_bracket:
	RULE_RIGHT_BR
	RULE_RIGHT_BR
;

// Rule DataTypes
data_types:
	'bool'
	| 'char'
	| 'short'
	| 'int'
	| 'long'
	| 'signed'
	| 'unsigned'
	| 'float'
	| 'double'
	| 'void'
	| 'alias'
;

// Rule TypeQualifier
type_qualifier:
	'const'
	| 'volatile'
;

// Rule StorageClassSpecifier
storage_class_specifier:
	'extern'
	| 'static'
	| 'register'
;

// Rule attribute_name
attribute_name:
	'NONE'
	| 'is_pc'
	| 'is_interlock_for'
	| 'do_not_synthesize'
	| 'enable'
	| 'no_cont'
	| 'cond'
	| 'flush'
;

// Rule StructOrUnion
struct_or_union:
	'struct'
	| 'union'
;

RULE_LEFT_BR : '[';

RULE_RIGHT_BR : ']';

RULE_BOOLEAN : ('true'|'false');

RULE_FLOAT : ('0'..'9')+ '.' ('0'..'9')* (('e'|'E') ('+'|'-')? ('0'..'9')+)? ('f'|'F'|'l'|'L')?;

RULE_INTEGER : (RULE_BINARYINT|RULE_HEXADECIMALINT|RULE_OCTALINT|RULE_DECIMALINT|RULE_VLOGINT) ('u'|'U')? (('l'|'L') ('l'|'L')?)?;

fragment RULE_BINARYINT : ('0b'|'0B') '0'..'1' ('_'? '0'..'1')*;

fragment RULE_OCTALINT : '0' '_'? '0'..'7' ('_'? '0'..'7')*;

fragment RULE_DECIMALINT : ('0'|'1'..'9' ('_'? '0'..'9')*);

fragment RULE_HEXADECIMALINT : ('0x'|'0X') ('0'..'9'|'a'..'f'|'A'..'F') ('_'? ('0'..'9'|'a'..'f'|'A'..'F'))*;

fragment RULE_VLOGINT : ('0'..'9')+ '\'' ('b' ('0'..'1')+|'o' ('0'..'7')+|'d' ('0'..'9')+|'h' ('0'..'9'|'a'..'f'|'A'..'F')+);

RULE_CHARCONST : ('u'|'U'|'L')? '\'' ('\\' .|~('\\'|'\''))* '\'';

RULE_INT : '~this one has been deactivated';

IDENTIFIER : '^'? ('a'..'z'|'A'..'Z'|'_') ('a'..'z'|'A'..'Z'|'_'|'0'..'9')*;

RULE_ENCSTRINGCONST : ('u8'|'u'|'U'|'L') '"' ('\\' .|~('\\'|'"'))* '"';

RULE_STRING : ('"' ('\\' .|~('\\'|'"'))* '"'|'\'' ('\\' .|~('\\'|'\''))* '\'');

RULE_ML_COMMENT : '/*' .*?'*/' -> skip;

RULE_SL_COMMENT : '//' ~('\n'|'\r')* ('\r'? '\n')? -> skip;

RULE_WS : (' '|'\t'|'\r'|'\n')+ -> skip;

RULE_ANY_OTHER : .;
