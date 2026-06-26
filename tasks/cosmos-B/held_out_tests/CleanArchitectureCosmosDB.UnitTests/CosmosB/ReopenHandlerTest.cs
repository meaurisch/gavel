using CleanArchitectureCosmosDB.Core.Entities;
using CleanArchitectureCosmosDB.Core.Exceptions;
using CleanArchitectureCosmosDB.UnitTests.CosmosB.TestDoubles;
using CleanArchitectureCosmosDB.WebAPI.Models.ToDoItem;
using System.Threading;
using System.Threading.Tasks;
using Xunit;

namespace CleanArchitectureCosmosDB.UnitTests.CosmosB
{
    public class ReopenHandlerTest
    {
        [Fact]
        public async Task Reopen_MarksCompletedItemIncomplete_AndPersists()
        {
            InMemoryToDoItemRepository repo = new InMemoryToDoItemRepository();
            ToDoItem item = new ToDoItem() { Id = "work:1", Category = "work", Title = "Reopen me" };
            item.MarkComplete();
            await repo.AddItemAsync(item);

            Reopen.CommandHandler handler = new Reopen.CommandHandler(repo);
            await handler.Handle(new Reopen.ReopenToDoItemCommand() { Id = "work:1" }, CancellationToken.None);

            ToDoItem stored = await repo.GetItemAsync("work:1");
            Assert.False(stored.IsCompleted);
        }

        [Fact]
        public async Task Reopen_UnknownId_ThrowsEntityNotFound()
        {
            InMemoryToDoItemRepository repo = new InMemoryToDoItemRepository();

            Reopen.CommandHandler handler = new Reopen.CommandHandler(repo);

            await Assert.ThrowsAsync<EntityNotFoundException>(() =>
                handler.Handle(new Reopen.ReopenToDoItemCommand() { Id = "missing:1" }, CancellationToken.None));
        }
    }
}
