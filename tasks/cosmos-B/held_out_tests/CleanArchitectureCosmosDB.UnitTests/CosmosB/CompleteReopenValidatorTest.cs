using CleanArchitectureCosmosDB.WebAPI.Models.ToDoItem;
using FluentValidation.Results;
using Xunit;

namespace CleanArchitectureCosmosDB.UnitTests.CosmosB
{
    /// <summary>
    ///     The complete/reopen commands carry only an Id, so an empty Id is the one
    ///     thing the validators must reject before a handler ever runs.
    /// </summary>
    public class CompleteReopenValidatorTest
    {
        [Fact]
        public void CompleteValidator_RejectsEmptyId()
        {
            Complete.CompleteToDoItemCommandValidator validator = new Complete.CompleteToDoItemCommandValidator();

            ValidationResult result = validator.Validate(new Complete.CompleteToDoItemCommand() { Id = "" });

            Assert.False(result.IsValid);
        }

        [Fact]
        public void CompleteValidator_AcceptsNonEmptyId()
        {
            Complete.CompleteToDoItemCommandValidator validator = new Complete.CompleteToDoItemCommandValidator();

            ValidationResult result = validator.Validate(new Complete.CompleteToDoItemCommand() { Id = "work:1" });

            Assert.True(result.IsValid);
        }

        [Fact]
        public void ReopenValidator_RejectsEmptyId()
        {
            Reopen.ReopenToDoItemCommandValidator validator = new Reopen.ReopenToDoItemCommandValidator();

            ValidationResult result = validator.Validate(new Reopen.ReopenToDoItemCommand() { Id = "" });

            Assert.False(result.IsValid);
        }

        [Fact]
        public void ReopenValidator_AcceptsNonEmptyId()
        {
            Reopen.ReopenToDoItemCommandValidator validator = new Reopen.ReopenToDoItemCommandValidator();

            ValidationResult result = validator.Validate(new Reopen.ReopenToDoItemCommand() { Id = "home:9" });

            Assert.True(result.IsValid);
        }
    }
}
